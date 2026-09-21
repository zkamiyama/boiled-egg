-- Execute only in a new, dedicated REAPER instance. Uses public API and rendering.
-- The caller sets BE_REAPER_JOB_FILE to a Lua table produced from validated JSON.
local manifest = assert(os.getenv('BE_REAPER_JOB_FILE'), 'missing job file')
local spec = dofile(manifest)
local function quote(s)
  return '"'..s:gsub('\\','\\\\'):gsub('"','\\"'):gsub('\n','\\n'):gsub('\r','\\r'):gsub('\t','\\t')..'"'
end
local function json(v)
  if type(v)=='string' then return quote(v) end
  if type(v)=='number' then assert(v==v and math.abs(v)<math.huge);return string.format('%.17g',v) end
  if type(v)=='boolean' then return tostring(v) end
  if type(v)=='table' then local out={};for k,val in pairs(v) do out[#out+1]=quote(tostring(k))..':'..json(val) end;table.sort(out);return '{'..table.concat(out,',')..'}' end
  return 'null'
end
local function write(path,obj)
 local f=assert(io.open(path,'w'));f:write(json(obj)..'\n');f:close()
end
local function takevalue(t,k,v)
 assert(reaper.SetMediaItemTakeInfo_Value(t,k,v),k)
 local got=reaper.GetMediaItemTakeInfo_Value(t,k);assert(math.abs(got-v)<1e-10,'take readback '..k);return got
end
local function itemvalue(t,k,v)
 assert(reaper.SetMediaItemInfo_Value(t,k,v),k)
 local got=reaper.GetMediaItemInfo_Value(t,k);assert(math.abs(got-v)<1e-10,'item readback '..k);return got
end
local function projectvalue(k,v)
 reaper.GetSetProjectInfo(0,k,v,true)
 local got=reaper.GetSetProjectInfo(0,k,0,false);assert(math.abs(got-v)<1e-10,'project readback '..k);return got
end
assert(reaper.GetAppVersion()==spec.version,'unexpected REAPER version')
local modes={}
for i=0,255 do local ok,name=reaper.EnumPitchShiftModes(i);if not ok then break end;if name then modes[tostring(i)]=name end end
write(spec.inventory,{version=reaper.GetAppVersion(),modes=modes})
local maps=io.open('/proc/self/maps','r');if maps then local dest=assert(io.open(spec.maps,'w'));dest:write(maps:read('*a'));dest:close();maps:close() end
local done=0
for _,job in ipairs(spec.jobs) do
 local receipt={id=job.id,status='failed',version=reaper.GetAppVersion(),plan_sha256=spec.plan_sha256}
 local ok,err=xpcall(function()
  local exists=io.open(job.output,'rb');if exists then exists:close();error('output already exists') end
  local available,name=reaper.EnumPitchShiftModes(job.mode)
  assert(available and name==job.mode_name,'mode unavailable or name mismatch')
  assert(reaper.EnumPitchShiftSubModes(job.mode,job.submode)==job.submode_name,'submode mismatch')
  while reaper.CountTracks(0)>0 do reaper.DeleteTrack(reaper.GetTrack(0,0)) end
  local master=reaper.GetMasterTrack(0);assert(reaper.TrackFX_GetCount(master)==0,'master FX')
  reaper.SetMediaTrackInfo_Value(master,'D_VOL',1);reaper.SetMediaTrackInfo_Value(master,'D_PAN',0)
  reaper.InsertTrackAtIndex(0,false);local track=reaper.GetTrack(0,0)
  assert(reaper.TrackFX_GetCount(track)==0)
  for k,v in pairs({D_VOL=1,D_PAN=0,D_PANLAW=1,B_MUTE=0,I_SOLO=0}) do assert(reaper.SetMediaTrackInfo_Value(track,k,v));assert(reaper.GetMediaTrackInfo_Value(track,k)==v,k) end
  local item=reaper.AddMediaItemToTrack(track);local take=reaper.AddTakeToMediaItem(item)
  local source=assert(reaper.PCM_Source_CreateFromFile(job.input),'source missing')
  local length,isqn=reaper.GetMediaSourceLength(source)
  assert(not isqn and math.abs(length-job.input_frames/job.rate)<.1/job.rate,'source duration')
  assert(reaper.GetMediaSourceSampleRate(source)==job.rate and reaper.GetMediaSourceNumChannels(source)==1,'source format')
  reaper.SetMediaItemTake_Source(take,source)
  receipt.item={};receipt.take={};receipt.project={}
  for k,v in pairs({D_POSITION=0,D_LENGTH=job.output_frames/job.rate,D_VOL=1,D_FADEINLEN=0,D_FADEOUTLEN=0,D_FADEINLEN_AUTO=-1,D_FADEOUTLEN_AUTO=-1,B_LOOPSRC=0}) do receipt.item[k]=itemvalue(item,k,v) end
  for k,v in pairs({D_PLAYRATE=1/job.time_ratio,D_PITCH=job.semitones,B_PPITCH=1,I_PITCHMODE=job.mode*65536+job.submode,D_VOL=1,D_PAN=0,D_PANLAW=1,D_STARTOFFS=0}) do receipt.take[k]=takevalue(take,k,v) end
  for k,v in pairs({PROJECT_SRATE=job.rate,PROJECT_SRATE_USE=1,RENDER_SRATE=job.rate,RENDER_CHANNELS=1,RENDER_BOUNDSFLAG=0,RENDER_STARTPOS=0,RENDER_ENDPOS=job.output_frames/job.rate,RENDER_SETTINGS=0,RENDER_TAILFLAG=0,RENDER_DITHER=0,RENDER_NORMALIZE=0,RENDER_ADDTOPROJ=0}) do receipt.project[k]=projectvalue(k,v) end
  reaper.GetSetProjectInfo_String(0,'RENDER_FILE',job.directory,true)
  reaper.GetSetProjectInfo_String(0,'RENDER_PATTERN',job.stem,true)
  -- Verified against actual output subtype FLOAT, not guessed from the name.
  reaper.GetSetProjectInfo_String(0,'RENDER_FORMAT','ZXZhdyAAAA==',true)
  reaper.GetSetProjectInfo_String(0,'RENDER_FORMAT2','',true)
  local _,format=reaper.GetSetProjectInfo_String(0,'RENDER_FORMAT','',false);assert(format=='ZXZhdyAAAA==','output format readback')
  local _,targets=reaper.GetSetProjectInfo_String(0,'RENDER_TARGETS','',false);assert(targets==job.output,'render target mismatch: '..tostring(targets))
  receipt.render_format=format;receipt.targets=targets;receipt.mode_name=name;receipt.submode_name=job.submode_name
  reaper.Main_SaveProjectEx(0,job.project,0)
  local started=reaper.time_precise();reaper.Main_OnCommand(41824,0);receipt.render_seconds=reaper.time_precise()-started
  local f=assert(io.open(job.output,'rb'),'missing render');receipt.output_bytes=f:seek('end');f:close()
  assert(receipt.output_bytes>44,'empty render')
  receipt.status='complete';done=done+1
 end,debug.traceback)
 if not ok then receipt.error=tostring(err) end
 write(job.receipt,receipt)
end
write(spec.done,{completed=done,attempts=#spec.jobs})
-- Only the isolated project owned by this script is saved or closed.
if #spec.jobs>0 then reaper.Main_SaveProjectEx(0,spec.jobs[#spec.jobs].project,0) end
reaper.Main_OnCommand(40004,0)
