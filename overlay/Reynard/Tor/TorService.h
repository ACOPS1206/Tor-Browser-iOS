#import <Foundation/Foundation.h>
NS_ASSUME_NONNULL_BEGIN
/// A process-local Tor client. Stopping disables Tor networking without enabling direct access.
@interface TBIOTorService : NSObject
@property(class, nonatomic, readonly) TBIOTorService *shared;
@property(nonatomic, readonly) NSString *statusText;
@property(nonatomic, readonly) NSInteger bootstrapProgress;
@property(nonatomic, readonly) BOOL ready;
@property(nonatomic, readonly) BOOL paused;
@property(nonatomic, readonly) NSString *relayInfoText;
- (void)refreshRelayInfo;
- (void)start;
- (void)pause;
- (void)requestNewCircuit;
@end
NS_ASSUME_NONNULL_END

