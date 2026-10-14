/* SPDX-License-Identifier: MPL-2.0 */
#ifndef TBIO_STATUS_POLL_H
#define TBIO_STATUS_POLL_H
#include <stdbool.h>
#include <stdint.h>

// Portable request lifetime model; deadlines use monotonic uptime.
typedef struct {
    uint64_t generation;
    double deadline;
    bool pending;
} TBIOStatusPoll;

static inline uint64_t TBIOPollBegin(TBIOStatusPoll *state, double now) {
    if (state->pending) return 0;
    state->pending = true;
    state->deadline = now + 10.0;
    return ++state->generation;
}
static inline void TBIOPollInvalidate(TBIOStatusPoll *state) {
    state->pending = false;
    ++state->generation;
}
static inline bool TBIOPollExpire(TBIOStatusPoll *state, uint64_t generation, double now) {
    if (!state->pending || state->generation != generation || now < state->deadline) return false;
    TBIOPollInvalidate(state);
    return true;
}
static inline bool TBIOPollAccept(TBIOStatusPoll *state, uint64_t generation, double now) {
    if (!state->pending || state->generation != generation || now >= state->deadline) return false;
    state->pending = false;
    return true;
}
static inline bool TBIOConnectionReady(bool valid, int progress, bool circuitEstablished) {
    return valid && progress == 100 && circuitEstablished;
}
#endif
