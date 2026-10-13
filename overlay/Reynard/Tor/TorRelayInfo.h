#import <Foundation/Foundation.h>

/// Only general, multi-hop exit circuits may be labeled Guard / Middle / Exit.
static inline BOOL TBIOIsDisplayableCircuit(NSString *status, NSString *purpose,
                                            NSArray<NSString *> *flags, NSUInteger nodeCount) {
    return [status isEqualToString:@"BUILT"] && [purpose isEqualToString:@"GENERAL"] && nodeCount >= 3
        && ![flags containsObject:@"IS_INTERNAL"] && ![flags containsObject:@"ONEHOP_TUNNEL"];
}

/// Format sanitized metadata only. Never accept raw control lines, site names,
/// SOCKS usernames/passwords or onion-service identifiers into the UI snapshot.
static inline NSString *TBIOFormatCircuit(NSString *circuitID, NSArray<NSDictionary<NSString *, NSString *> *> *nodes) {
    NSMutableArray<NSString *> *lines = [NSMutableArray arrayWithObject:[NSString stringWithFormat:@"Circuit %@", circuitID ?: @"Unknown"]];
    for (NSUInteger index = 0; index < nodes.count; index++) {
        NSDictionary<NSString *, NSString *> *node = nodes[index];
        NSString *role = index == 0 ? @"Guard" : index == nodes.count - 1 ? @"Exit" : @"Middle";
        [lines addObject:[NSString stringWithFormat:@"%@ · %@\n%@\n%@", role,
            node[@"name"].length ? node[@"name"] : @"Unnamed relay",
            node[@"address"].length ? node[@"address"] : @"Address unavailable",
            node[@"fingerprint"].length ? node[@"fingerprint"] : @"Fingerprint unavailable"]];
    }
    return [lines componentsJoinedByString:@"\n\n"];
}
