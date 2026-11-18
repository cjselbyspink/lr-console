"""Stub test for the two-module starter (lr_starter.py).

Loads every event of the generated profiles into a Lua interpreter with the
Grid API stubbed out, then drives the logic: key selection, plugin replies
(mask / develop / crop), slider follow, the jog, and the EN16 knob map.

This proves the Lua parses and the logic does what the source says. It does
NOT prove anything about real hardware: element numbering, LED behaviour and
which events a module receives are all stubbed assumptions here.

    pip install lupa
    python3 build_all.py /tmp/st 1118-1630 flipped lr_starter
    python3 test_starter.py /tmp/st
"""
import json, sys
D = sys.argv[1] if len(sys.argv) > 1 else '/tmp/st'
from lupa import LuaRuntime
def load(path):
    prof=json.load(open(path)); return {c['controlElementNumber']:{e['event']:e['config'] for e in c['events']} for c in prof['configs']}
PRE = r'''
calls = {}
function gps(...) calls[#calls+1] = {...} end
function gpl(n) end  function gpn() return 0 end  function glsb(n) end
function midi_send(...) error("midi_send should not be called in the starter") end
function mkel(i)
  local t = {idx=i}
  return setmetatable(t, {__index=function(_,k) if not METH[k] then return nil end return function(...) return rawget(t,'_'..k) or 0 end end})
end
ele = {}
'''
PRE = 'METH = {'+','.join('%s=true'%n for n in ['bst', 'element_index', 'ema', 'emi', 'emo', 'epma', 'epmi', 'epmo', 'epse', 'epst', 'epva', 'ese', 'est', 'gen', 'glc', 'glp', 'ini', 'ldaf', 'ldft', 'ldsw', 'match', 'sub', 'timer_start', 'timer_stop'])+'}\n'+PRE
def run(path, n_el):
    lua=LuaRuntime(unpack_returned_tuples=True); lua.execute(PRE)
    ev=load(path); fn={}
    for el,evs in ev.items():
        for e,code in evs.items():
            f=lua.eval('function(src) local f,err = load("return function(self) "..src.."\\nend") if not f then error(err) end return f() end')(code)
            fn[(el,e)]=f
    lua.execute('for i=0,%d do ele[i]=mkel(i) end ele[255]=mkel(255)'%(n_el-1))
    g=lua.globals()
    lua.execute('function elidx(i) ele[i]._gei = i ele[i].gei = nil end')
    setup=lambda i: fn[(i,0)](g.ele[i]) if (i,0) in fn else None
    return lua,g,fn,setup
ok=lambda c,m: print(('PASS ' if c else 'FAIL ')+m) or (c or sys.exit(1))

# ---------------- syntax: every event of every starter profile compiles
import glob
for p in sorted(glob.glob(D + '/*.json')):
    lua,g,fn,setup=run(p, 17)
print('syntax: all events of', len(glob.glob(D + '/*.json')), 'profiles load')

# ---------------- VSN1 page 1
lua,g,fn,setup=run(D + '/Starter_Page_1_VSN1.json', 14)
lua.execute('for i=0,13 do local j=i ele[j].ini=function() end end')
for i in list(range(0,14))+[255]: setup(i)
for i in range(0,14): setup(i)            # the System ini loop's second pass
E8=g.ele[8]; T=lambda *a: lua.table_from(list(a))
ok(E8.l_b==2,'boot selects Exposure (slot 2): l_b=%s'%E8.l_b)
E8.eventrx_cb(E8,T(0,127,127),T(0,5,3),T(127,0,127),0); ok(E8.l_b==5,'own key 5 press selects Shadows')
E8.eventrx_cb(E8,T(0,127,127),T(0,1,3),T(0,0,127),0);  ok(E8.l_b==5,'key release does not select')
g.LrImportActive(1,"M","none","","",0,""); ok(g.mk==True and E8.l_b==2,'reply M: mask mode on, lands on Exposure')
g.LrImportActive(1,"M","none","local_Shadows","12",0,""); ok(E8.l_b==5,'mask echo local_Shadows selects slot 5')
g.LrImportActive(1,"D","none","","",0,""); ok(g.mk==False,'reply D: mask mode off')
g.LrImportActive(1,"D","none","Tint","7",0,""); ok(E8.l_b==1,'slider follow: Tint echo selects slot 1')
g.LrImportActive(1,"C","none","","",0,""); ok(g.rm==True,'reply C: jog straightens (rm)')
g.LrImportActive(1,"D","none","","",0,"")
E8.eventrx_cb(E8,T(0,126,127),T(0,7,2),T(1,0,127),0); ok(g.hx=="Warm/violet",'EN16 preset knob (element 7, upright) names Warm/violet: %s'%g.hx)
E8.eventrx_cb(E8,T(0,126,127),T(0,5,2),T(1,0,127),0); ok(E8.l_b==1,'EN16 HSL knob event does not change selection')
lua.execute('calls={}'); E8._epst=2064
for k in range(6): fn[(8,7)](E8)
c=g.calls[1]; ok(c is not None and c[2]=="develop" and c[3]=="Tint" and c[4]==10 and c[5]==1,'six jog events send one relative develop for Tint: %s %s %s'%(c[2],c[3],c[4]))
lua.execute('calls={}'); E8._bst=127; fn[(8,3)](E8); E8._bst=0; fn[(8,3)](E8)
c=g.calls[1]; ok(c[2]=="revert-param" and c[3]=="Tint",'tap sends revert-param Tint')
fn[(13,8)](g.ele[13]); ok(True,'LCD Draw runs')
g.LrImportActive(1,"M","none","","",0,""); fn[(13,8)](g.ele[13]); ok(True,'LCD Draw runs under Mask')

# ---------------- VSN1 page 4 (actions)
lua,g,fn,setup=run(D + '/Starter_Page_4_VSN1.json', 14)
for i in list(range(0,14))+[255]: setup(i)
for i in range(0,14): setup(i)
E8=g.ele[8]; T=lambda *a: lua.table_from(list(a))
ok(E8.l_b==8,'page 4: nothing selected (l_b=8)')
lua.execute('calls={}'); g.ele[1]._bst=127; fn[(1,3)](g.ele[1]); c=g.calls[1]
ok(c[2]=="next-photo",'page 4 key 1 sends next-photo')
E8.eventrx_cb(E8,T(0,127,127),T(0,1,3),T(127,0,127),0); ok(E8.l_b==8,'page 4 key press does not select')
lua.execute('calls={}'); E8._epst=2064
for k in range(6): fn[(8,7)](E8)
ok(g.calls[1] is None,'page 4 jog sends nothing outside Crop')
fn[(13,8)](g.ele[13]); ok(True,'page 4 LCD Draw runs')

# ---------------- EN16 upright
lua,g,fn,setup=run(D + '/Starter_EN16_HSL.json', 16)
lua.execute('for i=0,15 do ele[i]._gei=i end')
# element_index short name: find what the compiled code calls
src=json.dumps(json.load(open(D + '/Starter_EN16_HSL.json')))
name='element_index' if 'element_index' in src else 'gei'
lua.execute('for i=0,15 do ele[i]._%s=i end'%name)
setup(255)
for i in range(0,16): setup(i)
bands=['Red','Orange','Yellow','Green']; props=['HueAdjustment','SaturationAdjustment','LuminanceAdjustment']
good=True
for r in range(4):
    for c in range(4):
        e=g.ele[4*r+c]
        if c<3: good&= (e.p==props[c]+bands[r])
        else: good&= (e.p is None and e.s is not None)
ok(good,'EN16 upright: row r = %s, columns Hue/Sat/Lum/preset (uses %s)'%(bands,name))
lua.execute('calls={}'); e=g.ele[5]; e._est=65; fn[(5,2)](e); fn[(5,6)](e); c=g.calls[1]
ok(c[2]=="develop" and c[3]=="SaturationAdjustmentOrange" and c[4]==5 and c[5]==1,'row 2 col 2 knob, one click: Orange Sat +5')
lua.execute('calls={}'); e=g.ele[3]; e._bst=127; fn[(3,3)](e); c=g.calls[1]
ok(c[2]=="preset" and c[3]==210 and c[4]==20,'top-right knob press fires Teal/orange preset')
print('ALL PASS')
