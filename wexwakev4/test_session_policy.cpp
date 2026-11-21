#include "kern_yoga_hdmi2_session_policy.hpp"
#include <cassert>
#include <cstdio>
using YogaHDMI2Session::LowReconcile;
using YogaHDMI2Session::mayReconcileLow;
int main() {
    LowReconcile p {};
    assert(!mayReconcileLow(p));
    p={true,true,true,true,true,true,true,true,true,true,true,25,29,600000};
    assert(mayReconcileLow(p));
    {
        LowReconcile q=p; q.requested=false; assert(!mayReconcileLow(q));
        q=p; q.physicalHDMIB=false; assert(!mayReconcileLow(q));
        q=p; q.knownPipe1=false; assert(!mayReconcileLow(q));
        q=p; q.exactAOC=false; assert(!mayReconcileLow(q));
        q=p; q.provenHighSession=false; assert(!mayReconcileLow(q));
        q=p; q.sameCompleteBase=false; assert(!mayReconcileLow(q));
        q=p; q.hadNativeDozeWake=false; assert(!mayReconcileLow(q));
        q=p; q.priorHighStatus10=false; assert(!mayReconcileLow(q));
        q=p; q.freshCTA=false; assert(!mayReconcileLow(q));
        q=p; q.currentHDMISCDC=false; assert(!mayReconcileLow(q));
        q=p; q.sourceHasHighFlags=false; assert(!mayReconcileLow(q));
        q=p; q.failedGeneration=0; assert(!mayReconcileLow(q));
        q=p; q.failedGeneration=29; assert(!mayReconcileLow(q));
        q=p; q.currentGeneration=25; assert(!mayReconcileLow(q));
        q=p; q.maxTMDSKHz=340000; assert(!mayReconcileLow(q));
        q=p; q.maxTMDSKHz=600001; assert(!mayReconcileLow(q));
    }
    std::puts("PASS R3: stale high-mode reconciliation requires confirmed native wake, prior status10, fresh CTA, identical sink, and source flags");
}
