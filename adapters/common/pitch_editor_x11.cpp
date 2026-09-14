#include "pitch_editor.hpp"
#include <X11/Xatom.h>
#include <X11/keysym.h>
#include <X11/Xutil.h>
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
namespace boiled_egg::plugin {
namespace {constexpr std::array<unsigned,6> rows{Pitch,Fine,Formant,FormantFine,Volume,Pan};
constexpr std::array<int,6> ys{176,230,312,366,434,488};
std::string formatted(unsigned p,float v){char s[64];if(p==Wet||p==Dry)std::snprintf(s,sizeof(s),"%.0f %%",100*v);
 else if(p==Fine||p==FormantFine)std::snprintf(s,sizeof(s),"%+.1f",double(v));
 else std::snprintf(s,sizeof(s),"%+.2f",double(v));return s;}}
unsigned long PitchEditor::color(const char* rgb) noexcept {XColor c{};return XParseColor(display_,DefaultColormap(display_,DefaultScreen(display_)),rgb,&c)&&XAllocColor(display_,DefaultColormap(display_,DefaultScreen(display_)),&c)?c.pixel:BlackPixel(display_,DefaultScreen(display_));}
bool PitchEditor::attach(unsigned long parent){
 if(display_||!parent)return false;display_=XOpenDisplay(nullptr);if(!display_)return false;
 bg_=color("#edf0ec");panel_=color("#fafbf8");ink_=color("#1d3530");muted_=color("#66756e");track_=color("#d3dad2");accent_=color("#c77c25");soft_=color("#f7ead6");border_=color("#b7c3b8");
 window_=XCreateSimpleWindow(display_,parent,0,0,width_,height_,0,border_,bg_);if(!window_){detach();return false;}
 XStoreName(display_,window_,"boiled egg - Pitch and Formant");
 const Atom info=XInternAtom(display_,"_XEMBED_INFO",False);unsigned long data[2]={0,1};XChangeProperty(display_,window_,info,info,32,PropModeReplace,reinterpret_cast<unsigned char*>(data),2);
 XSelectInput(display_,window_,ExposureMask|ButtonPressMask|ButtonReleaseMask|PointerMotionMask|(host_keyboard_?0:KeyPressMask)|StructureNotifyMask|FocusChangeMask);
 gc_=XCreateGC(display_,window_,0,nullptr);if(!gc_||!load_fonts()){detach();return false;}
 dirty_=true;XFlush(display_);return true;
}
bool PitchEditor::load_fonts() noexcept {
 const double scale=std::min(double(width_)/default_width,double(height_)/default_height);
 char name[128];std::snprintf(name,sizeof(name),"-adobe-helvetica-medium-r-normal--%d-0-0-0-p-0-iso8859-1",std::max(12,int(14*scale)));
 auto* regular=XLoadQueryFont(display_,name);if(!regular)regular=XLoadQueryFont(display_,"fixed");
 std::snprintf(name,sizeof(name),"-adobe-helvetica-bold-r-normal--%d-0-0-0-p-0-iso8859-1",std::max(20,int(24*scale)));
 auto* heading=XLoadQueryFont(display_,name);if(!heading)heading=XLoadQueryFont(display_,"fixed");
 if(!regular||!heading){if(regular)XFreeFont(display_,regular);if(heading)XFreeFont(display_,heading);return false;}
 if(font_)XFreeFont(display_,font_);if(heading_)XFreeFont(display_,heading_);font_=regular;heading_=heading;return true;
}
void PitchEditor::detach() noexcept {if(!display_)return;end();if(gc_)XFreeGC(display_,gc_);if(font_)XFreeFont(display_,font_);if(heading_)XFreeFont(display_,heading_);
 if(window_)XDestroyWindow(display_,window_);XCloseDisplay(display_);display_=nullptr;window_=0;gc_=nullptr;font_=heading_=nullptr;shown_=false;}
void PitchEditor::show(bool on) noexcept {if(!display_)return;if(!on)end();shown_=on;if(on)XMapWindow(display_,window_);else XUnmapWindow(display_,window_);dirty_=true;XFlush(display_);}
bool PitchEditor::resize(unsigned w,unsigned h) noexcept {if(w<760||h<560||w>1800||h>1280)return false;width_=w;height_=h;if(display_){XResizeWindow(display_,window_,w,h);(void)load_fonts();}dirty_=true;return true;}
void PitchEditor::box(int x,int y,int w,int h,unsigned long c) noexcept {XSetForeground(display_,gc_,c);XFillRectangle(display_,window_,gc_,sx(x),sy(y),unsigned(sx(w)),unsigned(sy(h)));}
void PitchEditor::line(int x1,int y1,int x2,int y2,unsigned long c) noexcept {XSetForeground(display_,gc_,c);XDrawLine(display_,window_,gc_,sx(x1),sy(y1),sx(x2),sy(y2));}
void PitchEditor::text(int x,int y,const std::string& s,unsigned long c,bool heading) noexcept {XSetForeground(display_,gc_,c);XSetFont(display_,gc_,(heading?heading_:font_)->fid);XDrawString(display_,window_,gc_,sx(x),sy(y),s.data(),int(s.size()));}
bool PitchEditor::enabled(unsigned p,const Values& v) const noexcept {return (p!=Formant&&p!=FormantFine)||(v[Backend]==1&&v[Policy]!=0);}
void PitchEditor::range(unsigned p,const Values& v,float& lo,float& hi) const noexcept {
 lo=parameters[p].min;hi=parameters[p].max;const float limit=v[Backend]==1?12.f:24.f;
 if(p==Pitch){lo=std::max(lo,-limit-v[Fine]*.01f);hi=std::min(hi,limit-v[Fine]*.01f);}
 if(p==Fine){lo=std::max(lo,(-limit-v[Pitch])*100.f);hi=std::min(hi,(limit-v[Pitch])*100.f);}
 if(p==Formant){lo=std::max(lo,-12.f-v[FormantFine]*.01f);hi=std::min(hi,12.f-v[FormantFine]*.01f);}
 if(p==FormantFine){lo=std::max(lo,(-12.f-v[Formant])*100.f);hi=std::min(hi,(12.f-v[Formant])*100.f);}
}
bool PitchEditor::begin(unsigned p) noexcept {end();const auto v=callbacks_.values(callbacks_.user);if(!enabled(p,v)||!callbacks_.edit(callbacks_.user,p,v[p],Gesture::Begin))return false;active_=int(p);focus_=int(p);dirty_=true;return true;}
void PitchEditor::value(unsigned p,float v) noexcept {const auto values=callbacks_.values(callbacks_.user);float lo,hi;range(p,values,lo,hi);v=std::clamp(v,lo,hi);
 (void)callbacks_.edit(callbacks_.user,p,v,Gesture::Value);dirty_=true;}
void PitchEditor::end() noexcept {if(active_>=0){const auto v=callbacks_.values(callbacks_.user);callbacks_.edit(callbacks_.user,unsigned(active_),v[unsigned(active_)],Gesture::End);}active_=-1;editing_=false;edit_text_.clear();dirty_=true;}
void PitchEditor::mouse(int x,int y,int button,bool motion) noexcept {
 const auto v=callbacks_.values(callbacks_.user);
 if(motion){if(active_<0||editing_)return;const auto p=unsigned(active_);float lo,hi;range(p,v,lo,hi);
  const float fraction=p==Wet||p==Dry?std::clamp((470.f-y)/294.f,0.f,1.f):std::clamp((x-410.f)/312.f,0.f,1.f);
  value(p,lo+fraction*(hi-lo));return;}
 if(button!=1&&button!=4&&button!=5)return;
 if(x>=226&&x<355&&y>=105&&y<137){if(begin(Bypass)){value(Bypass,v[Bypass]?0:1);end();}return;}
 if(x>=737&&x<858&&y>=105&&y<137){ // Reset values, not the selected engine/configuration.
  for(unsigned p=0;p<Backend;++p)if(begin(p)){value(p,parameters[p].initial);end();}return;
 }
 for(unsigned p:{Backend,Quality,Policy}){const int left=p==Backend?224:p==Quality?470:637,right=p==Backend?451:p==Quality?618:860;
  if(x>=left&&x<right&&y>=550&&y<580){const int choices=p==Backend?2:3;for(int step=1;step<=choices;++step){auto next=v;next[p]=float((int(v[p])+step)%choices);if(valid_values(next)){if(begin(p)){value(p,next[p]);end();}break;}}return;}}
 if(y<140||y>512)return;
 for(unsigned p:{Wet,Dry}){const int left=p==Wet?36:107;if(x>=left&&x<left+57){if(begin(p)){value(p,button==1?std::clamp((470.f-y)/294.f,0.f,1.f):v[p]+(button==4?.01f:-.01f));if(button!=1)end();}return;}}
 for(unsigned r=0;r<rows.size();++r){const auto p=rows[r];if(y<ys[r]-18||y>ys[r]+21||x<220)continue;
  if(!begin(p))return;
  if(x>=748&&x<847&&button==1){editing_=true;edit_text_=formatted(p,v[p]);if(!host_keyboard_)XSetInputFocus(display_,window_,RevertToParent,CurrentTime);dirty_=true;return;}
  float lo,hi;range(p,v,lo,hi);
  if(button==4||button==5){const float unit=p==Fine||p==FormantFine?1.f:p==Pan?.01f:.1f;value(p,v[p]+(button==4?unit:-unit));end();}
  else value(p,lo+std::clamp((x-410.f)/312.f,0.f,1.f)*(hi-lo));return;
 }
}
void PitchEditor::key(XKeyEvent& event) noexcept {
 char chars[32]{};KeySym symbol=0;const int n=XLookupString(&event,chars,sizeof(chars),&symbol,nullptr);
 (void)key_input(symbol,n?chars[0]:0,(event.state&ShiftMask)!=0,(event.state&ControlMask)!=0);
}
bool PitchEditor::key_input(unsigned long symbol,char ascii,bool shift,bool control) noexcept {
 if(editing_){if(symbol==XK_Escape){end();return true;}if(symbol==XK_Return||symbol==XK_KP_Enter){char* endptr=nullptr;const auto v=std::strtof(edit_text_.c_str(),&endptr);
   if(endptr!=edit_text_.c_str()&&*endptr=='\0'&&std::isfinite(v))value(unsigned(active_),v);end();return true;}
  if(symbol==XK_BackSpace){if(!edit_text_.empty())edit_text_.pop_back();dirty_=true;return true;}
  if(control&&(symbol==XK_a||symbol==XK_A||ascii=='a'||ascii=='A')){edit_text_.clear();dirty_=true;return true;}
  if(!control&&edit_text_.size()<20&&((ascii>='0'&&ascii<='9')||ascii=='+'||ascii=='-'||ascii=='.')){edit_text_+=ascii;dirty_=true;return true;}
  return false;
 }
 if(symbol==XK_Tab){focus_=(focus_+int(Backend)+(shift?-1:1))%int(Backend);dirty_=true;return true;}
 if(symbol==XK_Left||symbol==XK_Down||symbol==XK_Right||symbol==XK_Up||symbol==XK_Home){const unsigned p=unsigned(focus_);const auto v=callbacks_.values(callbacks_.user);
  float unit=parameters[p].stepped?1.f:p==Fine||p==FormantFine?1.f:p==Wet||p==Dry||p==Pan?.01f:.1f;if(shift&&!parameters[p].stepped)unit*=.1f;
  if(begin(p)){value(p,symbol==XK_Home?parameters[p].initial:v[p]+((symbol==XK_Left||symbol==XK_Down)?-unit:unit));end();return true;}}
 return false;
}
void PitchEditor::pump() noexcept {
 if(!display_)return;for(unsigned n=0;n<256&&XPending(display_);++n){XEvent e{};XNextEvent(display_,&e);
  if(e.type==Expose)dirty_=true;
  else if(e.type==ConfigureNotify){width_=unsigned(std::max(1,e.xconfigure.width));height_=unsigned(std::max(1,e.xconfigure.height));dirty_=true;}
  else if(e.type==ButtonPress)mouse(int(e.xbutton.x*default_width/width_),int(e.xbutton.y*default_height/height_),int(e.xbutton.button),false);
  else if(e.type==MotionNotify)mouse(int(e.xmotion.x*default_width/width_),int(e.xmotion.y*default_height/height_),1,true);
  else if(e.type==ButtonRelease&&!editing_)end();
  else if(e.type==KeyPress&&!host_keyboard_)key(e.xkey);
  // Acquiring explicit keyboard focus can first emit NotifyPointer for the
  // implicit pointer focus. It is not loss of the editor's new focus.
  else if(e.type==FocusOut&&e.xfocus.mode==NotifyNormal&&
          e.xfocus.detail!=NotifyPointer&&e.xfocus.detail!=NotifyPointerRoot&&e.xfocus.detail!=NotifyInferior)end();
 }
 const auto v=callbacks_.values(callbacks_.user);if(v!=last_)dirty_=true;
 if(shown_&&dirty_)draw();
}
void PitchEditor::draw() noexcept {
 if(!display_)return;const auto v=callbacks_.values(callbacks_.user);last_=v;
 box(0,0,900,640,bg_);box(0,0,900,80,ink_);text(28,36,"boiled egg",panel_,true);text(29,61,"PITCH + FORMANT   /   one shifter",track_);
 text(596,31,"INPUT-CLOCK AUTOMATION",soft_);char label[96];std::snprintf(label,sizeof(label),"Stereo  |  Delay %u samples",callbacks_.latency(callbacks_.user));text(596,58,label,panel_);
 box(22,98,154,496,panel_);text(37,128,"OUTPUT MIX",ink_);text(46,157,"Wet",muted_);text(116,157,"Dry",muted_);
 for(unsigned p:{Wet,Dry}){const int center=p==Wet?64:136;box(center-3,176,6,294,track_);const int y=470-int(v[p]*294);
  box(center-3,y,6,470-y,accent_);box(center-16,y-7,32,14,ink_);text(center-28,511,formatted(p,v[p]),ink_);}
 text(34,549,"Dry is delay",muted_);text(34,568,"compensated",muted_);
 box(199,98,679,428,panel_);box(226,105,129,32,v[Bypass]?track_:soft_);text(241,126,v[Bypass]?"Bypassed":"Enabled",ink_);
 box(737,105,121,32,bg_);text(753,126,"Reset voice",ink_);
 text(371,126,"VOICE 1",muted_);
 for(unsigned r=0;r<rows.size();++r){const auto p=rows[r];const int y=ys[r];const bool on=enabled(p,v);const auto col=on?ink_:muted_;
  text(224,y+5,parameters[p].name,col);float lo,hi;range(p,v,lo,hi);box(410,y-3,312,6,track_);
  const int pos=410+int(312*std::clamp((v[p]-lo)/std::max(1e-20f,hi-lo),0.f,1.f));const int zero=410+int(312*(-lo)/std::max(1e-20f,hi-lo));
  line(zero,y-9,zero,y+10,border_);if(on){box(std::min(pos,zero),y-3,std::abs(pos-zero),6,accent_);box(pos-6,y-10,12,20,ink_);}
  box(748,y-16,99,31,editing_&&active_==int(p)?soft_:bg_);text(758,y+5,editing_&&active_==int(p)?edit_text_:formatted(p,v[p]),col);
  text(753,y+21,parameters[p].unit,muted_);if(focus_==int(p))line(224,y+13,365,y+13,accent_);
 }
 line(224,269,851,269,border_);text(224,289,"Independent formant control",muted_);
 text(224,537,"PROCESSING  /  manual selection - restart required for changes",muted_);
 for(unsigned p:{Backend,Quality,Policy}){const int x=p==Backend?224:p==Quality?470:637,w=p==Backend?227:p==Quality?148:223;
  box(x,550,w,30,panel_);text(x+10,570,choice(p,int(v[p])),ink_);text(x,601,parameters[p].name,muted_);}
 const char* error=callbacks_.error(callbacks_.user);
 if(error&&*error)text(22,625,error,accent_);
 else if(callbacks_.pending(callbacks_.user))text(22,625,"Pending processing change: host restart / deactivate-reactivate required",accent_);
 else text(22,625,v[Backend]==1?"PV PREVIEW  |  +/-12 st  |  10 ms pitch ramp  |  same fixed delay at every pitch":"WSOLA  |  +/-24 st  |  presets and automation keep the original pitch parameter",muted_);
 dirty_=false;XFlush(display_);
}
}
