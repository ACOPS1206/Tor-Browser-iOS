#include <assert.h>
#include "TorStatusPoll.h"

int main(void) {
    TBIOStatusPoll state = {0};
    uint64_t first = TBIOPollBegin(&state, 100.0);
    assert(first && !TBIOPollBegin(&state, 101.0)); // overlapping poll rejected
    assert(!TBIOPollExpire(&state, first, 109.99));
    assert(TBIOPollExpire(&state, first, 110.0));
    assert(!TBIOPollAccept(&state, first, 111.0)); // stale completion after timeout
    uint64_t second = TBIOPollBegin(&state, 112.0);
    assert(second != first);
    assert(!TBIOPollAccept(&state, first, 113.0)); // wrong reply cannot consume new poll
    assert(state.pending);
    assert(TBIOPollAccept(&state, second, 113.0));
    assert(!TBIOPollAccept(&state, second, 113.0)); // duplicate callback
    uint64_t third = TBIOPollBegin(&state, 114.0);
    TBIOPollInvalidate(&state); // pause, stop or controller replacement
    assert(!TBIOPollAccept(&state, third, 115.0));
    uint64_t fourth = TBIOPollBegin(&state, 120.0);
    assert(!TBIOPollAccept(&state, fourth, 130.0)); // reply at deadline is stale
    assert(TBIOPollExpire(&state, fourth, 130.0));
    assert(TBIOConnectionReady(true, 100, true));
    assert(!TBIOConnectionReady(false, 100, true)); // malformed status
    assert(!TBIOConnectionReady(true, 99, true));
    assert(!TBIOConnectionReady(true, 100, false)); // bootstrap alone isn't readiness
    assert(!TBIOConnectionReady(true, 101, true));
    return 0;
}
