// Yoga A7A0 HDMI 2.0 experiment: NO new donor routes.
// Requires existing Display13 GMBUS, watermark and MMIO write wrappers.
// No globals are accessed when experiment is off.
#ifndef KERN_YOGA_HDMI2_CANDIDATE_HPP
#define KERN_YOGA_HDMI2_CANDIDATE_HPP
#include "hdmi2_8bpc_plan.hpp"
#include "hdmi2_scdc_prepare.hpp"
#include <IOKit/i2c/IOI2CInterface.h>
#include <IOKit/graphics/IOGraphicsTypes.h>

struct YogaHDMI2Live {
    OSObject *port {};
    Display13HDMI::Caps caps {};
    uint32_t generation {};
    bool baseSeen {};
};
static YogaHDMI2Live yogaHDMI2Live {};
static volatile uint32_t yogaHDMI2ArmedPipe=3; // 0..2=armed; 3=off
static volatile uint32_t yogaHDMI2Writes {};
static mach_vm_address_t yogaHDMI2NativeI2C {};

static inline void yogaHDMI2ObserveDDC(OSObject *port,uint32_t block,
                                       const uint8_t *data,bool success,
                                       IOSimpleLock *lock) {
    if(!port || !lock || !data || (block!=1 && (block<2 || block>8)))return;
    IOSimpleLockLock(lock);
    if(block==1) {
        yogaHDMI2Live.port=port;
        yogaHDMI2Live.baseSeen=success;
        ++yogaHDMI2Live.generation;
        yogaHDMI2Live.caps={};
        __atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);
    } else if(yogaHDMI2Live.baseSeen && yogaHDMI2Live.port==port) {
        if(success) {
            const auto c=Display13HDMI::extension(data,128);
            yogaHDMI2Live.caps=Display13HDMI::combine(yogaHDMI2Live.caps,c);
        }
        ++yogaHDMI2Live.generation;
        // Any fresh DDC extension invalidates a previous source-mode token:
        // the sink capability/cache generation may have changed.
        __atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);
    }
    IOSimpleLockUnlock(lock);
}

// Native controller I2C: 0xA8 8-bit address, register pointer followed
// by repeated-start read. Never use Display13 register-write callbacks for I2C.
struct YogaHDMI2Bus {
    IOService *controller {},*fb {};
    OSObject *port {};
    IOSimpleLock *lock {};
    uint32_t fbIndex {},ddc {},expectedGeneration {};
    using Native=uint32_t (*)(void *,uint32_t,uint32_t,uint32_t,IOI2CBusTiming *,IOI2CRequest *);
    Native native {};
    uint64_t generation() const {
        if(!lock)return 0;
        IOSimpleLockLock(lock);
        const auto value=yogaHDMI2Live.generation;
        IOSimpleLockUnlock(lock);
        return value;
    }
    bool connected() const {
        if(!controller || !port || !lock || !native)return false;
        auto recursive=Display13FBMemory::field<IORecursiveLock *>(controller,0x9B8);
        if(!recursive || !IORecursiveLockHaveLock(recursive))return false;
        IOSimpleLockLock(lock);
        const bool valid=yogaHDMI2Live.baseSeen && yogaHDMI2Live.port==port &&
            yogaHDMI2Live.generation==expectedGeneration;
        IOSimpleLockUnlock(lock);
        return valid;
    }
    bool send(bool read,uint8_t reg,uint8_t &value) {
        if(!connected())return false;
        IOI2CRequest request {};
        uint8_t bytes[2] {reg,value};
        request.sendTransactionType=1;
        request.sendAddress=0xA8;
        request.sendBuffer=reinterpret_cast<uintptr_t>(bytes);
        request.sendBytes=read?1:2;
        if(read) {
            request.replyTransactionType=1;
            request.replyAddress=0xA8;
            request.replyBuffer=reinterpret_cast<uintptr_t>(&value);
            request.replyBytes=1;
        }
        request.result=kIOReturnNotReady;
        const auto status=native(controller,fbIndex,ddc,0,nullptr,&request);
        return !status && !request.result && connected();
    }
    bool read(uint8_t reg,uint8_t &v){return send(true,reg,v);}
    bool write(uint8_t reg,uint8_t v){return send(false,reg,v);}
};

// Caller is the EXISTING Display13 pipe WM callback, after it drops the
// WM power lock. The native recursive display owner lock must still be held.
// Do not force modeset return values; no MMIO or SCDC if any guard fails.
static inline uint32_t yogaHDMI2TryPrepare(IOService *controller,IOService *fb,
       OSObject *path,uint64_t pixelHz, bool allowWrite,IOSimpleLock *lock) {
    if(!controller || !fb || !path || !lock || !yogaHDMI2NativeI2C)return 1;
    if(fb->getMetaClass()->getClassSize()<0x4B90 ||
       path->getMetaClass()->getClassSize()<0x3650)return 2;
    auto port=Display13FBMemory::field<OSObject *>(path,0x3648);
    if(!port || port->getMetaClass()->getClassSize()<0x580)return 3;
    auto config=Display13FBMemory::field<uint32_t *>(port,0x548);
    if(!config || config[0]!=1 || config[2]!=2)return 4; // physical B HDMI
    auto recursive=Display13FBMemory::field<IORecursiveLock *>(controller,0x9B8);
    if(!recursive || !IORecursiveLockHaveLock(recursive))return 5;
    if(Display13FBMemory::field<void *>(fb,0x1D0)!=controller ||
       Display13FBMemory::field<void *>(path,0x32B0)!=fb)return 6;
    const auto pipe=Display13FBMemory::field<uint32_t>(path,0x3640);
    if(pipe>=3)return 7;
    // Never inject SCDC traffic into the proven normal 4K30 boot. Only
    // restore low mode if this same pipe was previously armed for high TMDS.
    if(allowWrite && pixelHz<=YogaHDMI2::HighTMDSHz &&
       __atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE)!=pipe)return 52;
    // The precise current path shadow is read, not guessed from HDMI EDID.
    const auto ctl=Display13FBMemory::field<uint32_t>(path,0x12C);
    const bool hdmi=((ctl>>24)&7)==0 && ((ctl>>20)&7)==0;
    if(!hdmi)return 8; // reject YCbCr420 or deep colour if not proven
    if(!pixelHz || pixelHz>600000000ULL)return 9;
    Display13HDMI::Caps caps;uint32_t generation;
    IOSimpleLockLock(lock);
    const bool same=yogaHDMI2Live.port==port && yogaHDMI2Live.baseSeen;
    caps=yogaHDMI2Live.caps;generation=yogaHDMI2Live.generation;
    IOSimpleLockUnlock(lock);
    if(!same || !caps.valid || !caps.hdmi || !caps.scdc ||
       caps.maxKHz<=340000)return 10;
    // Require exact native controller owner. We never obtain or hold the
    // Display13 power lock while invoking native I2C.
    auto &state=display13FBPower;
    if(!state.lock)return 11;
    IOLockLock(state.lock);
    const bool ready=controller==state.controller && state.engineEnabled &&
        !state.clockFaulted && !state.memoryFaulted && !state.clockStopped &&
        state.access==Display13FBMemory::field<void *>(controller,0xC40);
    IOLockUnlock(state.lock);
    if(!ready)return 12;
    YogaHDMI2Bus bus {controller,fb,port,lock,
       Display13FBMemory::field<uint32_t>(fb,0x1DC),config[1],
       generation,reinterpret_cast<YogaHDMI2Bus::Native>(yogaHDMI2NativeI2C)};
    YogaHDMI2::Request q {};
    q.physicalHDMI=true;q.verifiedEDID=true;
    q.encoding=YogaHDMI2::Encoding::RGB; // source's Deep8 profile; 420 explicitly excluded by path
    q.bitsPerPixel=24;q.pixelClockHz=pixelHz;q.sinkMaxTMDSKHz=caps.maxKHz;
    q.sinkSCDCPresent=caps.scdc;q.sourceSCDCVerified=true;
    const auto plan=YogaHDMI2::plan(q);
    if(!plan.accepted)return 13+static_cast<uint32_t>(plan.reject);
    if(!allowWrite)return plan.highTMDS?50:51; // read-only observe
    // Every >340MHz transaction confirms the HDMI Forum sink response.
    const auto transaction=YogaHDMI2::prepareSCDC(bus,plan,caps.scdc);
    if(!transaction.complete)return 30+static_cast<uint32_t>(transaction.error);
    if(plan.highTMDS)
        __atomic_store_n(&yogaHDMI2ArmedPipe,pipe,__ATOMIC_RELEASE);
    else
        __atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);
    return plan.highTMDS?100:101;
}
#endif
