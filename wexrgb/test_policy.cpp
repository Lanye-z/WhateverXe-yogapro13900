#include "kern_yoga_hdmi_color_policy.hpp"
#include <cassert>
#include <cstdio>
using namespace YogaHDMIColorPolicy;
int main() {
    auto d=decide(2,10,Variant::Audit,true,false);
    assert(d.mode==2 && d.depth==10 && d.outcome==Outcome::Observe);
    d=decide(2,10,Variant::Bpc8,true,false);
    assert(d.mode==2 && d.depth==8 && d.outcome==Outcome::Changed);
    d=decide(2,30,Variant::Bpc8,true,false);
    assert(d.mode==2 && d.depth==24 && d.outcome==Outcome::Changed);
    d=decide(2,30,Variant::Rgb8,true,false);
    assert(d.mode==1 && d.depth==24 && d.outcome==Outcome::Changed);
    d=decide(2,10,Variant::Rgb8,false,false);
    assert(d.mode==2 && d.depth==10 && d.outcome==Outcome::NotQualified);
    d=decide(2,10,Variant::Rgb8,true,true);
    assert(d.mode==2 && d.depth==10 && d.outcome==Outcome::Conflict);
    d=decide(2,3,Variant::Rgb8,true,false);
    assert(d.mode==2 && d.depth==3 && d.outcome==Outcome::UnknownDepth);
    d=decide(0,10,Variant::Rgb8,true,false);
    assert(d.mode==0 && d.depth==10 && d.outcome==Outcome::NotQualified);
    d=decide(1,8,Variant::Rgb8,true,false);
    assert(d.mode==1 && d.depth==8 && d.outcome==Outcome::Already8);
    std::puts("PASS: A7A0 HDMI colour policy guarded experiment helper");
}
