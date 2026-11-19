struct Display13HDMICache {void *port {};Display13HDMI::Caps caps;uint64_t generation {};Display13HDMI::EDIDCache edid;};
static Display13HDMICache display13HDMICache[7]; // protected by tglAUXLock
bool XE::display13HDMISCDCOwned(void *controller,void *framebuffer,void *object) {
    auto s=callbackXE;auto fb=static_cast<IOService *>(framebuffer);auto path=static_cast<OSObject *>(object);
    if(!s->display13FramebufferRequested || !s->display13BootReady || !s->display13HDMII2CRequest ||
       !fb || !path || fb->getMetaClass()->getClassSize()<0x4B90 || path->getMetaClass()->getClassSize()<0x3650 ||
       controller!=s->adlnTopologyController || Display13FBMemory::field<void *>(fb,0x1D0)!=controller ||
       Display13FBMemory::field<void *>(path,0x32B0)!=fb ||
       !s->display13HDMIPort(Display13FBMemory::field<OSObject *>(path,0x3648)))return false;
    auto lock=Display13FBMemory::field<IORecursiveLock *>(controller,0x9B8);
    if(!lock || !IORecursiveLockHaveLock(lock))return false;
    auto &c=display13FBPower;if(!c.lock)return false;
    IOLockLock(c.lock);
    const bool ready=controller==c.controller && c.engineEnabled && adlnWriterMappingBound() &&
        !c.clockFaulted && !c.memoryFaulted && !c.bridge.state.faulted && !c.bridge.state.suspended;
    IOLockUnlock(c.lock);return ready;
}
bool XE::display13HDMISCDCTransfer(void *controller,void *fb,void *path,bool read,uint8_t reg,uint8_t &value) {
    if(!display13HDMISCDCOwned(controller,fb,path))return false;
    auto port=Display13FBMemory::field<OSObject *>(path,0x3648);
    auto cfg=Display13FBMemory::field<uint32_t *>(port,0x548);
    IOI2CRequest request {};uint8_t bytes[2] {reg,value};
    static_assert(offsetof(IOI2CRequest,sendBuffer)==0x44 && offsetof(IOI2CRequest,replyBuffer)==0x4C,"exact donor I2C pointer ABI");
    static_assert(offsetof(IOI2CRequest,result)==0x1C && offsetof(IOI2CRequest,replyBytes)==0x38,"exact donor I2C result ABI");
    if(read)Display13HDMI::scdcReadRequest(request,bytes,value);
    else Display13HDMI::scdcWriteRequest(request,bytes);
    request.result=kIOReturnNotReady;
    using Native=uint32_t (*)(void *,uint32_t,uint32_t,uint32_t,IOI2CBusTiming *,IOI2CRequest *);
    // Keep the donor's I2C command gate. Never wait for DDC under c.lock or
    // the AUX cache lock; native modesetting already owns its display mutex.
    const auto status=reinterpret_cast<Native>(callbackXE->display13HDMII2CRequest)(controller,
        Display13FBMemory::field<uint32_t>(fb,0x1DC),cfg[1],0,nullptr,&request);
    const bool stillOwned=display13HDMISCDCOwned(controller,fb,path);
    uint64_t observation[] {1,cfg[0],cfg[1],read,reg,status,uint32_t(request.result),
        request.sendBytes,request.replyBytes,value,stillOwned};
    IORegistryEntry::getRegistryRoot()->setProperty("N97FBHDMISCDCTransfer",observation,sizeof(observation));
    return !status && !request.result && (read ? request.sendBytes==1 && request.replyBytes==1 : request.sendBytes==2) && stillOwned;
}
bool XE::prepareDisplay13HDMISCDC(void *controller,void *fb,void *path,const void *timing) {
    if(!display13HDMISCDCOwned(controller,fb,path) || !timing || !tglAUXLock)return false;
    auto port=Display13FBMemory::field<OSObject *>(path,0x3648);
    auto cfg=Display13FBMemory::field<uint32_t *>(port,0x548);if(cfg[0]>=7)return false;
    Display13HDMI::Caps caps;uint64_t generation=0;
    IOSimpleLockLock(tglAUXLock);
    if(display13HDMICache[cfg[0]].port==port) {
        caps=display13HDMICache[cfg[0]].caps;generation=display13HDMICache[cfg[0]].generation;
    }
    IOSimpleLockUnlock(tglAUXLock);
    const auto t=static_cast<const IODetailedTimingInformationV2 *>(timing);
    // The donor only computes a correct TMDS PLL for uncompressed 8-bpc
    // RGB/444. SDR normalization happens before its clock/depth mapping.
    auto &control=*reinterpret_cast<uint32_t *>(static_cast<uint8_t *>(path)+0x12C);
    const auto plan=Display13HDMI::linkPlan(control,t->pixelEncoding,t->bitsPerColorComponent,
        uint64_t(caps.maxKHz)*1000,caps.valid,caps.scdc);
    if(!plan.valid)return false;
    struct IO {
        void *controller,*fb,*path;OSObject *port;uint32_t ddi;uint64_t generation;
        bool connected(){
            const bool owned=XE::display13HDMISCDCOwned(controller,fb,path);
            IOSimpleLockLock(tglAUXLock);
            const auto cachedPort=display13HDMICache[ddi].port;
            const auto cachedGeneration=display13HDMICache[ddi].generation;
            const bool same=cachedPort==port && cachedGeneration==generation;
            IOSimpleLockUnlock(tglAUXLock);
            uint64_t observation[] {1,ddi,owned,same,reinterpret_cast<uint64_t>(port),
                reinterpret_cast<uint64_t>(cachedPort),generation,cachedGeneration};
            IORegistryEntry::getRegistryRoot()->setProperty("N97FBHDMISCDCConnection",observation,sizeof(observation));
            return owned && same;
        }
        bool read(uint8_t reg,uint8_t &v){return XE::display13HDMISCDCTransfer(controller,fb,path,true,reg,v);}
        bool write(uint8_t reg,uint8_t v){return XE::display13HDMISCDCTransfer(controller,fb,path,false,reg,v);}
    } io{controller,fb,path,port,cfg[0],generation};
    const auto result=Display13HDMI::negotiateSCDC(io,t->pixelClock,plan.maximumHz,plan.scdc);
    // 0x12C feeds TRANS_DDI_FUNC_CTL; 0x128 instead feeds TRANS_CLK_SEL.
    // Preserve native port, BPC, mode and enable bits. No live MMIO rewrite.
    const bool complete=result.complete && io.connected();
    if(complete)
        control=(control&~0xD1U)|result.sourceFlags;
    uint64_t record[] {1,cfg[0],t->pixelClock,caps.maxKHz,caps.scdc,complete,
        result.before,result.wanted,result.changed,result.restored,result.sourceFlags,control};
    IORegistryEntry::getRegistryRoot()->setProperty("N97FBHDMISCDC",record,sizeof(record));
    return complete;
}
uint32_t XE::wrapDisplay13HDMIOnline(IOService *fb,OSObject *path,uint8_t *online,uint8_t *changed) {
    const auto result=FunctionCast(wrapDisplay13HDMIOnline,callbackXE->orgDisplay13HDMIOnline)(fb,path,online,changed);
    auto s=callbackXE;
    if(result || !online || !*online || !fb || !path || !tglAUXLock ||
       fb->getMetaClass()->getClassSize()<0x4B90 || path->getMetaClass()->getClassSize()<0x3650 ||
       Display13FBMemory::field<void *>(fb,0x1D0)!=s->adlnTopologyController)return result;
    auto port=Display13FBMemory::field<OSObject *>(path,0x3648);
    if(!s->display13HDMIPort(port))return result;
    auto cfg=Display13FBMemory::field<uint32_t *>(port,0x548);
    if(cfg[0]>=7)return result;
    // Native getOnlineInfo reads the first CTA block. Some sinks put the
    // HDMI Forum VSDB in a later extension. Read only advertised missing
    // blocks through the same bounded native DDC path before publishing the
    // timing range. Never hold the cache spinlock across DDC transactions.
    for(unsigned block=2;block<=Display13HDMI::EDIDCache::Extensions+1;++block) {
        IOSimpleLockLock(tglAUXLock);
        const bool missing=display13HDMICache[cfg[0]].port==port &&
            display13HDMICache[cfg[0]].edid.missing(block);
        const auto generation=display13HDMICache[cfg[0]].generation;
        IOSimpleLockUnlock(tglAUXLock);
        if(!missing)continue;
        uint8_t data[128];
        if(wrapAlderLakeNPortDDC(port,block,data,false))break;
        IOSimpleLockLock(tglAUXLock);
        const bool same=display13HDMICache[cfg[0]].port==port &&
            display13HDMICache[cfg[0]].generation==generation+1;
        IOSimpleLockUnlock(tglAUXLock);
        if(!same)return result;
    }
    Display13HDMI::Caps caps;
    IOSimpleLockLock(tglAUXLock);
    if(display13HDMICache[cfg[0]].port==port)caps=display13HDMICache[cfg[0]].caps;
    IOSimpleLockUnlock(tglAUXLock);
    auto &limit=*reinterpret_cast<uint64_t *>(reinterpret_cast<uint8_t *>(fb)+0x4368);
    const auto before=limit;limit=Display13HDMI::sourceLimitHz(caps,before,s->display13HDMII2CRequest && s->display13FBOutputHooksReady);
    uint64_t record[] {1,cfg[0],caps.valid,caps.hdmi,caps.scdc,caps.maxKHz,before,limit};
    char key[64];snprintf(key,sizeof(key),"N97FBHDMISourceLimit%u",cfg[0]);
    IORegistryEntry::getRegistryRoot()->setProperty(key,record,sizeof(record));
    return result;
}
