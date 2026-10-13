#import "TorService.h"
#include <stdlib.h>
#include <string.h>
#import <Tor/TORConfiguration.h>
#import <Tor/TORController.h>
#import <Tor/TORThread.h>

@interface TBIOTorService ()
@property(nonatomic) TORConfiguration *configuration;
@property(nonatomic) TORThread *torThread;
@property(nonatomic) TORController *controller;
@property(nonatomic) NSTimer *timer;
@property(nonatomic) NSString *statusText;
@property(nonatomic) NSInteger bootstrapProgress;
@property(nonatomic) BOOL ready;
@property(nonatomic) BOOL paused;
@property(nonatomic) BOOL authenticating;
@property(nonatomic) BOOL authenticated;
@property(nonatomic) NSUInteger attempts;
@end

@implementation TBIOTorService
+ (TBIOTorService *)shared {
    static TBIOTorService *instance;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ instance = [TBIOTorService new]; instance.statusText = @"Tor 시작 전 / Not connected"; });
    return instance;
}
- (void)publish {
    NSAssert(NSThread.isMainThread, @"Tor state must be published on main thread");
    [NSNotificationCenter.defaultCenter postNotificationName:@"TBIO.TorStatus" object:self];
}
- (void)start {
    NSAssert(NSThread.isMainThread, @"Start Tor on main thread");
    const char *mode = getenv("TBIO_ROUTING_MODE");
    if (mode && strcmp(mode, "never") == 0) {
        self.ready = NO;
        self.statusText = @"Tor 꺼짐 — 직접 연결 / Tor off — direct connection";
        [self publish];
        return;
    }
    if (self.torThread) {
        if (self.paused && self.authenticated) {
            [self.controller setConfForKey:@"DisableNetwork" withValue:@"0" completion:^(BOOL success, NSError *error) {
                dispatch_async(dispatch_get_main_queue(), ^{
                    if (success) { self.paused = NO; self.statusText = @"Tor 다시 연결 중 / Reconnecting"; }
                    else { self.statusText = @"Tor 재연결 실패 / Resume failed"; }
                    [self publish];
                });
            }];
        }
        return;
    }
    NSURL *base = [NSFileManager.defaultManager URLsForDirectory:NSApplicationSupportDirectory inDomains:NSUserDomainMask].firstObject;
    NSURL *directory = [base URLByAppendingPathComponent:@"EmbeddedTor" isDirectory:YES];
    NSError *error = nil;
    if (![NSFileManager.defaultManager createDirectoryAtURL:directory withIntermediateDirectories:YES attributes:@{NSFileProtectionKey: NSFileProtectionCompleteUntilFirstUserAuthentication} error:&error]) {
        self.statusText = @"Tor 저장소 생성 실패 / Storage failed"; [self publish]; return;
    }
    // Old control files refer to a previous process and must never be used for authentication.
    for (NSString *name in @[@"controlport", @"control_auth_cookie"]) {
        [NSFileManager.defaultManager removeItemAtURL:[directory URLByAppendingPathComponent:name] error:nil];
    }
    TORConfiguration *config = [TORConfiguration new];
    config.dataDirectory = directory;
    config.ignoreMissingTorrc = YES;
    config.avoidDiskWrites = YES;
    config.clientOnly = YES;
    config.cookieAuthentication = YES;
    config.autoControlPort = YES;
    config.options = [@{
        @"SocksPort": @"127.0.0.1:19050 IsolateSOCKSAuth IsolateDestAddr IsolateDestPort",
        @"SafeSocks": @"1", @"TestSocks": @"1", @"ClientRejectInternalAddresses": @"1",
        @"ClientDNSRejectInternalAddresses": @"1", @"SafeLogging": @"1",
        @"ClientUseIPv6": @"1", @"Log": @"warn stdout"
    } mutableCopy];
    self.configuration = config;
    self.torThread = [[TORThread alloc] initWithConfiguration:config];
    [self.torThread start];
    self.statusText = @"Tor 연결 준비 중 / Starting";
    self.timer = [NSTimer scheduledTimerWithTimeInterval:1.0 target:self selector:@selector(tick:) userInfo:nil repeats:YES];
    [self publish];
}
- (void)tick:(NSTimer *)timer {
    if (self.paused) return;
    if (self.torThread.isFinished) {
        self.ready = NO; self.statusText = @"Tor 종료됨 — 앱을 다시 실행하세요 / Tor stopped; restart app";
        [timer invalidate]; [self publish]; return;
    }
    if (!self.authenticated) {
        if (self.authenticating) return;
        self.attempts++;
        NSData *cookie = self.configuration.cookie;
        if (!cookie || ![NSFileManager.defaultManager fileExistsAtPath:self.configuration.controlPortFile.path]) {
            if (self.attempts == 60) { self.statusText = @"Tor 시작 지연 / Startup delayed"; [self publish]; }
            return;
        }
        NSString *controlLine = [NSString stringWithContentsOfURL:self.configuration.controlPortFile encoding:NSUTF8StringEncoding error:nil];
        NSRegularExpression *controlPattern = [NSRegularExpression regularExpressionWithPattern:@"^PORT=127\\.0\\.0\\.1:([0-9]+)\\s*$" options:0 error:nil];
        NSTextCheckingResult *address = controlLine ? [controlPattern firstMatchInString:controlLine options:0 range:NSMakeRange(0, controlLine.length)] : nil;
        if (!address) return; // The control file may still be being written.
        NSInteger port = [[controlLine substringWithRange:[address rangeAtIndex:1]] integerValue];
        if (port < 1 || port > 65535) return;
        self.authenticating = YES;
        // Control socket connection is local only; no DNS or external connection is made here.
        TORController *controller = [[TORController alloc] initWithSocketHost:@"127.0.0.1" port:(in_port_t)port];
        NSError *error = nil;
        if (!controller.connected && ![controller connect:&error]) { self.authenticating = NO; return; }
        self.controller = controller;
        [controller authenticateWithData:cookie completion:^(BOOL success, NSError *error) {
            dispatch_async(dispatch_get_main_queue(), ^{
                self.authenticating = NO; self.authenticated = success;
                if (!success) { [controller disconnect]; self.controller = nil; }
            });
        }];
        return;
    }
    [self.controller getInfoForKeys:@[@"status/bootstrap-phase", @"status/circuit-established"] completion:^(NSArray<NSString *> *values) {
        dispatch_async(dispatch_get_main_queue(), ^{
            if (self.paused) return;
            NSString *phase = [values.firstObject isKindOfClass:NSString.class] ? values.firstObject : @"";
            NSRegularExpression *regex = [NSRegularExpression regularExpressionWithPattern:@"PROGRESS=([0-9]+)" options:0 error:nil];
            NSTextCheckingResult *match = [regex firstMatchInString:phase options:0 range:NSMakeRange(0, phase.length)];
            if (match) self.bootstrapProgress = [[phase substringWithRange:[match rangeAtIndex:1]] integerValue];
            self.ready = self.bootstrapProgress == 100 && values.count > 1 && [values[1] isKindOfClass:NSString.class] && [values[1] isEqualToString:@"1"];
            self.statusText = self.ready ? @"Tor 연결됨 / Connected" : [NSString stringWithFormat:@"Tor 연결 중 / Connecting %ld%%", (long)self.bootstrapProgress];
            [self publish];
        });
    }];
}
- (void)pause {
    self.paused = YES; self.ready = NO; self.statusText = @"통신 차단됨 / Paused"; [self publish];
    [self.controller setConfForKey:@"DisableNetwork" withValue:@"1" completion:^(BOOL success, NSError *error) {
        if (!success) dispatch_async(dispatch_get_main_queue(), ^{
            self.paused = NO; self.statusText = @"일시 정지 실패 / Pause failed"; [self publish];
        });
    }];
}
- (void)requestNewCircuit {
    if (!self.authenticated || self.paused) return;
    // NEWNYM does not clear cookies, tabs, caches, or in-flight streams. It is NOT "New Identity".
    [self.controller resetConnection:^(BOOL success) {
        dispatch_async(dispatch_get_main_queue(), ^{
            self.statusText = success ? @"새 회로 요청됨 / Circuit requested" : @"회로 요청 실패 / Request failed";
            [self publish];
        });
    }];
}
@end

