#import <Foundation/Foundation.h>
#import "TorRelayInfo.h"

static void check(BOOL condition) { if (!condition) abort(); }
int main(void) {
    @autoreleasepool {
        check(TBIOIsDisplayableCircuit(@"BUILT", @"GENERAL", @[], 3));
        check(!TBIOIsDisplayableCircuit(@"EXTENDED", @"GENERAL", @[], 3));
        check(!TBIOIsDisplayableCircuit(@"BUILT", @"HS_CLIENT_REND", @[], 3));
        check(!TBIOIsDisplayableCircuit(@"BUILT", @"GENERAL", @[@"IS_INTERNAL"], 3));
        check(!TBIOIsDisplayableCircuit(@"BUILT", @"GENERAL", @[@"ONEHOP_TUNNEL"], 1));
        check(!TBIOIsDisplayableCircuit(@"BUILT", @"GENERAL", @[], 2));
        NSString *text = TBIOFormatCircuit(@"17", @[
            @{@"name": @"Alpha", @"address": @"203.0.113.1", @"fingerprint": @"AAAA"},
            @{@"name": @"Beta", @"address": @"2001:db8::2", @"fingerprint": @"BBBB"},
            @{@"name": @"Gamma", @"fingerprint": @"CCCC", @"socksPassword": @"secret"}]);
        check([text containsString:@"Circuit 17"] && [text containsString:@"Guard · Alpha"]);
        check([text containsString:@"Middle · Beta"] && [text containsString:@"Exit · Gamma"]);
        check([text containsString:@"Address unavailable"] && [text containsString:@"2001:db8::2"]);
        check(![text containsString:@"secret"]);
        check([TBIOFormatCircuit(nil, @[@{}, @{}, @{}]) containsString:@"Fingerprint unavailable"]);
        puts("Relay filtering and formatting: 11 cases passed");
    }
    return 0;
}
