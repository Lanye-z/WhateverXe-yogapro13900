void XE::configureDisplay13HDMISDR(void *framebuffer,void *timing) {
    auto s=callbackXE;auto fb=static_cast<IOService *>(framebuffer);
    // RDI is unspecified at this exact donor call site. Use the supplied FB
    // owner and active path, before its timing copy feeds PLL/BPC math.
    if(!s->display13FramebufferRequested || !s->display13BootReady || !fb || !timing ||
       fb->getMetaClass()->getClassSize()<0x4B90 ||
       Display13FBMemory::field<void *>(fb,0x1D0)!=s->adlnTopologyController)return;
    const auto slot=Display13FBMemory::field<int32_t>(fb,0x3FD8)==-1 ? 0x49F0 : 0x4A08;
    auto path=Display13FBMemory::field<OSObject *>(fb,slot);
    if(!path || path->getMetaClass()->getClassSize()<0x3650 ||
       Display13FBMemory::field<void *>(path,0x32B0)!=fb ||
       !s->display13HDMIPort(Display13FBMemory::field<OSObject *>(path,0x3648)))return;
    const auto encoding=Display13FBMemory::field<uint16_t>(timing,0x88);
    const auto range=Display13FBMemory::field<uint16_t>(timing,0x8E);
    auto &depth=*reinterpret_cast<uint16_t *>(static_cast<uint8_t *>(timing)+0x8A);
    const auto before=depth;depth=Display13HDMI::sdrDepth(encoding,depth,range);
    uint64_t record[] {1,encoding,range,before,depth};
    IORegistryEntry::getRegistryRoot()->setProperty("N97FBHDMISDRDepth",record,sizeof(record));
}
void XE::configureDisplay13HDMIGCP(void *controller,void *framebuffer,void *object) {
    auto s=callbackXE;auto &c=display13FBPower;
    auto fb=static_cast<IOService *>(framebuffer);auto path=static_cast<OSObject *>(object);
    if(!s->display13FramebufferRequested || s->xeProfile.display!=XELP::Display::XeLPD ||
       !s->display13BootReady || !c.lock || !fb || !path ||
       fb->getMetaClass()->getClassSize()<0x4B90 || path->getMetaClass()->getClassSize()<0x3650 ||
       controller!=c.controller || Display13FBMemory::field<void *>(fb,0x1D0)!=controller ||
       Display13FBMemory::field<void *>(path,0x32B0)!=fb)return;
    auto port=Display13FBMemory::field<OSObject *>(path,0x3648);
    if(!s->display13HDMIPort(port))return;
    const auto pipe=Display13FBMemory::field<uint32_t>(path,0x3640);if(pipe>=3)return;
    Display13HDMI::GCPResult result;
    IOLockLock(c.lock);
    if(controller==c.controller && c.engineEnabled && adlnWriterMappingBound()) {
        Display13FBDBUFIO io {c.map};
        if(Display13FBIRQ::powered(io.read(Display13Power::Driver),pipe))result=Display13HDMI::ensureGCP(io,pipe);
    }
    IOLockUnlock(c.lock);
    uint64_t record[] {1,pipe,result.eligible,result.complete,result.depth,result.control,result.gcp,result.writes};
    char key[64];snprintf(key,sizeof(key),"N97FBHDMIGCP%u",pipe);
    IORegistryEntry::getRegistryRoot()->setProperty(key,record,sizeof(record));
}
