#ifndef BOILED_EGG_PLUGIN_PITCH_EDITOR_HPP
#define BOILED_EGG_PLUGIN_PITCH_EDITOR_HPP
#include "pitch_controls.hpp"
#include <string>
#ifdef BOILED_EGG_PLUGIN_X11
#include <X11/Xlib.h>
namespace boiled_egg::plugin {
enum class Gesture {Begin,Value,End};
struct EditorCallbacks {
 void* user{};
 Values (*values)(void*) noexcept{};
 bool (*edit)(void*,unsigned,float,Gesture) noexcept{};
 unsigned (*latency)(void*) noexcept{};
 bool (*pending)(void*) noexcept{};
 const char* (*error)(void*) noexcept{};
};
// X11/XEmbed child only. All methods are GUI/main-thread, never DSP callbacks.
// The host timer pumps events; no private GUI thread or callback-side X calls.
class PitchEditor {
public:
 explicit PitchEditor(EditorCallbacks cb):callbacks_(cb){}
 ~PitchEditor(){detach();}
 PitchEditor(const PitchEditor&)=delete;PitchEditor& operator=(const PitchEditor&)=delete;
 bool attach(unsigned long parent);
 void host_keyboard(bool enabled) noexcept {host_keyboard_=enabled;}
 bool key_input(unsigned long symbol,char ascii,bool shift,bool control) noexcept;
 void focus_lost() noexcept {end();}
 void detach() noexcept;
 void show(bool on) noexcept;
 bool resize(unsigned w,unsigned h) noexcept;
 void pump() noexcept;
 void draw() noexcept;
 unsigned long window() const noexcept {return window_;}
 static constexpr unsigned default_width=900,default_height=640;
private:
 bool load_fonts() noexcept;
 void text(int x,int y,const std::string& s,unsigned long color,bool heading=false) noexcept;
 void box(int x,int y,int w,int h,unsigned long color) noexcept;
 void line(int x1,int y1,int x2,int y2,unsigned long color) noexcept;
 unsigned long color(const char* rgb) noexcept;
 bool enabled(unsigned p,const Values& v) const noexcept;
 void range(unsigned p,const Values& v,float& lo,float& hi) const noexcept;
 bool begin(unsigned p) noexcept;
 void value(unsigned p,float v) noexcept;
 void end() noexcept;
 void mouse(int x,int y,int button,bool motion) noexcept;
 void key(XKeyEvent& event) noexcept;
 int sx(int x) const noexcept {return int(double(x)*width_/default_width);}
 int sy(int y) const noexcept {return int(double(y)*height_/default_height);}
 EditorCallbacks callbacks_;
 Display* display_{};Window window_{};GC gc_{};XFontStruct *font_{},*heading_{};
 unsigned width_{default_width},height_{default_height};
 unsigned long bg_{},panel_{},ink_{},muted_{},track_{},accent_{},soft_{},border_{};
 Values last_=defaults();
 int active_{-1},focus_{Pitch};bool editing_{},dirty_{true},shown_{},host_keyboard_{};
 std::string edit_text_;
};
}
#endif
#endif
