#include "pitch_editor.hpp"
#include <X11/keysym.h>
#include <chrono>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <thread>
using namespace boiled_egg::plugin;
namespace {
void require(bool value,const char* message){if(!value)throw std::runtime_error(message);}
struct Model {
 Values values=defaults(); int open=0;unsigned starts=0,ends=0;
 static Values read(void* p)noexcept{return static_cast<Model*>(p)->values;}
 static bool edit(void* p,unsigned i,float v,Gesture g)noexcept{
  auto& m=*static_cast<Model*>(p);
  if(g==Gesture::Begin){if(m.open)return false;++m.starts;++m.open;return true;}
  if(g==Gesture::End){if(m.open!=1)return false;++m.ends;--m.open;return true;}
  auto next=m.values;next[i]=v;if(!valid_values(next))return false;m.values=next;return true;
 }
 EditorCallbacks callbacks(){return {this,read,edit,[](void*)noexcept{return 1664u;},[](void*)noexcept{return false;},[](void*)noexcept{return "";}};}
};
void pump(Display* display,PitchEditor& editor){
 XSync(display,False);
 // X events cross two client connections. Wait only in this GUI test harness.
 for(int i=0;i<5;++i){editor.pump();std::this_thread::sleep_for(std::chrono::milliseconds(1));}
}
void button(Display* d,PitchEditor& editor,unsigned type,unsigned button,int x,int y){
 XEvent e{};e.xbutton.type=type;e.xbutton.display=d;e.xbutton.window=editor.window();
 e.xbutton.root=DefaultRootWindow(d);e.xbutton.x=x;e.xbutton.y=y;e.xbutton.button=button;e.xbutton.same_screen=True;
 require(XSendEvent(d,editor.window(),False,type==ButtonPress?ButtonPressMask:ButtonReleaseMask,&e),"send button");pump(d,editor);
}
void focus(Display* d,PitchEditor& editor,int mode){
 XEvent e{};e.xfocus.type=FocusOut;e.xfocus.display=d;e.xfocus.window=editor.window();e.xfocus.mode=mode;e.xfocus.detail=NotifyNonlinear;
 require(XSendEvent(d,editor.window(),False,FocusChangeMask,&e),"send focus");pump(d,editor);
}
}
int main(){try{
 Display* display=XOpenDisplay(nullptr);require(display,"X display required");
 Window parent=XCreateSimpleWindow(display,DefaultRootWindow(display),0,0,900,640,0,0,0);XMapWindow(display,parent);XSync(display,False);
 Model model;PitchEditor editor(model.callbacks());require(editor.attach(parent),"attach editor");editor.show(true);pump(display,editor);
 button(display,editor,ButtonPress,1,500,176);require(model.open==1,"drag begins gesture");
 editor.show(false);require(model.open==0&&model.starts==model.ends,"hiding editor must end active host gesture");
 editor.show(true);pump(display,editor);
 button(display,editor,ButtonPress,1,780,176);require(model.open==1,"numeric edit begins gesture");
 focus(display,editor,NotifyGrab);require(model.open==1,"temporary focus grab must not cancel editing");
 focus(display,editor,NotifyNormal);require(model.open==0,"focus loss must end numeric host gesture");
 model.values[Wet]=.75f;button(display,editor,ButtonPress,5,64,323);
 require(std::abs(model.values[Wet]-.74f)<1e-6f,"wheel decrements wet relative to value, not pointer position");
 require(model.open==0,"wheel gesture balanced");
 button(display,editor,ButtonPress,4,64,450);require(std::abs(model.values[Wet]-.75f)<1e-6f,"wheel increment independent of pointer height");
 // Wheel leaves focus on Wet. Four tabs reach the binary Bypass control.
 for(int i=0;i<4;++i)require(editor.key_input(XK_Tab,0,false,false),"tab handled");
 require(editor.key_input(XK_Right,0,false,false)&&model.values[Bypass]==1.f,"binary control keyboard step must be integral");
 require(editor.key_input(XK_Home,0,false,false)&&model.values[Bypass]==0.f,"home restores binary default");
 button(display,editor,ButtonPress,1,64,323);button(display,editor,ButtonRelease,1,64,323);
 require(std::abs(model.values[Wet]-.5f)<1e-6f,"normal fader remains positional");
 require(editor.resize(1125,800),"resize");pump(display,editor);
 button(display,editor,ButtonPress,5,80,403);require(std::abs(model.values[Wet]-.49f)<1e-6f,"scaled wheel coordinates");
 require(model.open==0&&model.starts==model.ends,"all accepted host gestures closed");
 editor.detach();XDestroyWindow(display,parent);XCloseDisplay(display);
 std::cout<<model.starts<<" balanced gestures; hide/focus, relative wheel, keyboard and scaled input passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
