#import "TorService.h"
#import "TorRelayInfo.h"
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
@property(nonatomic) NSString *relayInfoText;
@property(nonatomic) BOOL relayQueryPending;
@property(nonatomic) NSUInteger relayGeneration;
@end

@implementation TBIOTorService
+ (TBIOTorService *)shared {
    static TBIOTorService *instance;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ instance = [TBIOTorService new]; instance.statusText = @"Not connected"; instance.relayInfoText = @"Connect to Tor to view relays."; });
    return instance;
}
- (void)publish {
    NSAssert(NSThread.isMainThread, @"Tor state must be published on main thread");
    if (!self.ready) {
        self.relayGeneration++;
        self.relayQueryPending = NO;
        self.relayInfoText = self.paused ? @"Tor is paused. Relay information is unavailable." : @"Connect to Tor to view relays.";
    }
    [NSNotificationCenter.defaultCenter postNotificationName:@"TBIO.TorStatus" object:self];
}
- (void)start {
    NSAssert(NSThread.isMainThread, @"Start Tor on main thread");
    const char *mode = getenv("TBIO_ROUTING_MODE");
    if (mode && strcmp(mode, "never") == 0) {
        self.ready = NO;
        self.statusText = @"Tor off — direct connection";
        [self publish];
        return;
    }
    if (self.torThread) {
        if (self.paused && self.authenticated) {
            [self.controller setConfForKey:@"DisableNetwork" withValue:@"0" completion:^(BOOL success, NSError *error) {
                dispatch_async(dispatch_get_main_queue(), ^{
                    if (success) { self.paused = NO; self.statusText = @"Reconnecting"; }
                    else { self.statusText = @"Resume failed"; }
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
        self.statusText = @"Storage failed"; [self publish]; return;
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
    self.statusText = @"Starting";
    self.timer = [NSTimer scheduledTimerWithTimeInterval:1.0 target:self selector:@selector(tick:) userInfo:nil repeats:YES];
    [self publish];
}
- (void)tick:(NSTimer *)timer {
    if (self.paused) return;
    if (self.torThread.isFinished) {
        self.ready = NO; self.statusText = @"Tor stopped; restart app";
        [timer invalidate]; [self publish]; return;
    }
    if (!self.authenticated) {
        if (self.authenticating) return;
        self.attempts++;
        NSData *cookie = self.configuration.cookie;
        if (!cookie || ![NSFileManager.defaultManager fileExistsAtPath:self.configuration.controlPortFile.path]) {
            if (self.attempts == 60) { self.statusText = @"Startup delayed"; [self publish]; }
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
            self.statusText = self.ready ? @"Connected" : [NSString stringWithFormat:@"Connecting %ld%%", (long)self.bootstrapProgress];
            [self publish];
        });
    }];
}

- (void)refreshRelayInfo {
    NSAssert(NSThread.isMainThread, @"Refresh relay info on main thread");
    if (!self.ready || self.paused || !self.authenticated) { [self publish]; return; }
    if (self.relayQueryPending) return;
    self.relayQueryPending = YES;
    NSUInteger generation = ++self.relayGeneration;
    TORController *controller = self.controller;
    self.relayInfoText = @"Loading relay information…";
    [self publish];
    // Bound the UI wait and reject any late response after pause, NEWNYM or timeout.
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 10 * NSEC_PER_SEC), dispatch_get_main_queue(), ^{
        if (generation != self.relayGeneration || !self.relayQueryPending) return;
        self.relayGeneration++;
        self.relayQueryPending = NO;
        self.relayInfoText = @"Relay information timed out. Tap Refresh Relays to retry.";
        [self publish];
    });
    [controller getInfoForKeys:@[@"circuit-status"] completion:^(NSArray<NSString *> *values) {
        // The framework can return NSNull despite its NSString generic annotation.
        NSString *raw = values.count == 1 && [values[0] isKindOfClass:NSString.class] ? values[0] : nil;
        NSMutableArray<TORCircuit *> *circuits = [NSMutableArray new];
        NSMutableOrderedSet<NSString *> *keys = [NSMutableOrderedSet new];
        for (TORCircuit *circuit in raw ? [TORCircuit circuitsFromString:raw] : @[]) {
            if (!TBIOIsDisplayableCircuit(circuit.status, circuit.purpose, circuit.buildFlags, circuit.nodes.count)) continue;
            [circuits addObject:circuit];
            for (TORNode *node in circuit.nodes) {
                // Accept only a 40-character hex fingerprint as a control-command argument.
                NSString *fingerprint = node.fingerprint;
                NSCharacterSet *hex = [NSCharacterSet characterSetWithCharactersInString:@"0123456789abcdefABCDEF"];
                if (fingerprint.length == 40 && [fingerprint rangeOfCharacterFromSet:hex.invertedSet].location == NSNotFound) {
                    [keys addObject:[@"ns/id/" stringByAppendingString:fingerprint]];
                }
            }
        }
        void (^finish)(NSArray<NSString *> *) = ^(NSArray<NSString *> *descriptors) {
            NSMutableDictionary<NSString *, NSString *> *lookup = [NSMutableDictionary new];
            for (NSUInteger index = 0; index < MIN(keys.count, descriptors.count); index++) {
                if ([descriptors[index] isKindOfClass:NSString.class]) lookup[keys[index]] = descriptors[index];
            }
            NSMutableArray<NSString *> *blocks = [NSMutableArray new];
            for (TORCircuit *circuit in circuits) {
                NSMutableArray<NSDictionary<NSString *, NSString *> *> *nodes = [NSMutableArray new];
                for (TORNode *node in circuit.nodes) {
                    NSString *descriptor = lookup[[@"ns/id/" stringByAppendingString:node.fingerprint ?: @""]];
                    if (descriptor) [node acquireIpAddressesFromNsResponse:descriptor];
                    [nodes addObject:@{@"name": node.nickName ?: @"", @"address": node.ipv4Address ?: node.ipv6Address ?: @"", @"fingerprint": node.fingerprint ?: @""}];
                }
                [blocks addObject:TBIOFormatCircuit(circuit.circuitId, nodes)];
            }
            dispatch_async(dispatch_get_main_queue(), ^{
                if (generation != self.relayGeneration || controller != self.controller || !self.ready || self.paused) return;
                self.relayQueryPending = NO;
                NSString *details = blocks.count ? [blocks componentsJoinedByString:@"\n\n────────\n\n"] : raw ? @"No built general-purpose circuits yet. Open a website, then refresh." : @"Relay information unavailable. Tap Refresh Relays to retry.";
                self.relayInfoText = details;
                [self publish];
            });
        };
        // Empty GETINFO requests are invalid. Missing descriptors leave fingerprints
        // visible and addresses explicitly unavailable rather than hiding the circuit.
        if (keys.count) [controller getInfoForKeys:keys.array completion:finish];
        else finish(@[]);
    }];
}

- (void)pause {
    self.paused = YES; self.ready = NO; self.statusText = @"Paused"; [self publish];
    [self.controller setConfForKey:@"DisableNetwork" withValue:@"1" completion:^(BOOL success, NSError *error) {
        if (!success) dispatch_async(dispatch_get_main_queue(), ^{
            self.paused = NO; self.statusText = @"Pause failed"; [self publish];
        });
    }];
}
- (void)requestNewCircuit {
    if (!self.authenticated || self.paused) return;
    self.relayGeneration++;
    self.relayQueryPending = NO;
    self.relayInfoText = @"Circuit change requested. Refresh relays for updated information.";
    [self publish];
    // NEWNYM does not clear cookies, tabs, caches, or in-flight streams. It is NOT "New Identity".
    [self.controller resetConnection:^(BOOL success) {
        dispatch_async(dispatch_get_main_queue(), ^{
            self.statusText = success ? @"Circuit requested" : @"Request failed";
            [self publish];
        });
    }];
}
@end


