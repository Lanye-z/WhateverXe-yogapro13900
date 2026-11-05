#include "kern_yoga_hdmi600.hpp"
#include <cassert>
#include <cstdint>
#include <cstring>
#include <vector>
#include <cstdio>
int main() {
 std::vector<uint8_t> image(YogaHDMI600::Site+sizeof(YogaHDMI600::Find)+1,0xcc);
 memcpy(image.data()+YogaHDMI600::Site,YogaHDMI600::Find,sizeof(YogaHDMI600::Find));
 assert(YogaHDMI600::matches(image.data(),image.size(),YogaHDMI600::Function));
 assert(!YogaHDMI600::matches(nullptr,image.size(),YogaHDMI600::Function));
 assert(!YogaHDMI600::matches(image.data(),image.size(),YogaHDMI600::Function+1));
 assert(!YogaHDMI600::matches(image.data(),YogaHDMI600::Site+sizeof(YogaHDMI600::Find),YogaHDMI600::Function));
 for(size_t i=0;i<sizeof(YogaHDMI600::Find);++i) {
  image[YogaHDMI600::Site+i]^=1;
  assert(!YogaHDMI600::matches(image.data(),image.size(),YogaHDMI600::Function));
  image[YogaHDMI600::Site+i]^=1;
 }
 const auto pristine=image;
 memcpy(image.data()+YogaHDMI600::Site,YogaHDMI600::Replace,sizeof(YogaHDMI600::Replace));
 for(size_t i=0;i<image.size();++i)if(image[i]!=pristine[i])assert(i>=0x2e780&&i<0x2e784);
 uint32_t rate=0;
 memcpy(&rate,image.data()+0x2e780,4);
 assert(rate==600000000);
 puts("PASS guard and 300->600MHz immediate-only replacement");
}
