-- LR Console fork — ProcessMessage.lua — drop (a), 27 Sep 2026.
--
-- Differences from the stock Grid Editor plugin, all on the reply path:
--
--  1. The reply carries board-useful state in the fields the package relays.
--     The package (index.js) builds the board script from NAMED fields and
--     ignores anything else, so the payload rides in the four string fields
--     the board has never used:
--
--        LrImportActive(id, isoSpeed, aperture, shutterSpeed, focalLength, rating, flag)
--                       id   MODULE    LABEL     PARAM         VALUE       0-5     P/""/R
--
--        MODULE  "L" library, "D" develop, else first letter of the module name
--        LABEL   "red" | "yellow" | "green" | "blue" | "purple" | "none"
--        PARAM   develop parameter name, or "" (unused until drop b)
--        VALUE   its value as text, or ""          (unused until drop b)
--
--     This is a deliberate hack: the fields keep their JSON names so the
--     package's relay is untouched. Nothing on the board ever read ISO or
--     aperture. The clean route is a forked package; not needed yet.
--
--  2. A watcher task (LrcStartWatcher, started from Start.lua) polls the
--     current module, target photo, label, rating and flag every 0.3 s and
--     sends the same reply whenever any of them changes — so mouse changes,
--     photo switches and module switches reach the board too.
--
--  3. New incoming commands:  state            -> reply now
--                             color-toggle,X   -> label X, or none if already X
--                             reset-param,NAME -> LrDevelopController.resetToDefault(NAME)  [untested]
--
--  NOTE: SDK calls yield to Lightroom's scheduler, so plain pcall() fails with
--  "Yielding is not allowed within a C or metamethod call". Every protected
--  call here is LrTasks.pcall, which exists for exactly this. (Drop a.1 fix.)
--
--  Drop (c), 27 Sep 2026: `view,library` = E/G on one key (see the view handler).
--
--  Drop (b), 27 Sep 2026:
--   - `develop` ticks echo PARAM and VALUE back to the board through an echo
--     task that sends at most every 0.1 s and always sends the final value.
--     Reason `echo` in the log.
--   - Turn-start capture: the first tick on a parameter records its value
--     before the delta; the turn lasts until a tick on a DIFFERENT parameter,
--     revert/reset, or a change of photo (pauses don't end it).
--   - Slider follow: the known parameters are polled 5x/s in Develop; a
--     change the board didn't make is echoed with reason `follow`. `revert-param,NAME` sets
--     it back there; `reset-param,NAME` goes to Adobe's default. Both echo.
--   - Unlabelled photos report "gray" from the SDK; normalised to "none".
--
--  4. Every reply is logged: REPLY <reason> <json>, or REPLY <reason> FAILED <err>.
--     Log file: ~/Library/Logs/Adobe/Lightroom/LrClassicLogs/LRConsole.log
--
-- Everything else is the stock handler, verbatim.

local LrLogger = import 'LrLogger'
local logger = LrLogger('LRConsole')
logger:enable("logfile")

local LrSelection = import "LrSelection"
local LrApplicationView = import "LrApplicationView"
local LrApplication = import "LrApplication"
local LrUndo = import "LrUndo"
local LrDevelopController = import "LrDevelopController"
local LrTasks = import 'LrTasks'

-- ---------------------------------------------------------------- state ----

-- Last state sent to (or seen by) the board. The watcher compares against it.
local last = { id = -1, module = "", tool = "", label = "", rating = -1, flag = 99 }
local turnStart = {}             -- param -> value before the first tick of a turn
local turnParam = nil            -- the parameter the current turn is on
local snap = {}                  -- param -> last value known to the plugin (follow)
local snapValid = false
local lastView = ""   -- last view this plugin set; see the library key

-- 0.2.8: in Develop the letter also carries the selected tool — "C" crop,
-- "M" masking — so BU16 can gate its crop keys and VSN2 can show the mode.
local function moduleCode(name, tool)
  if name == "library" then return "L" end
  if name == "develop" then
    if tool == "crop" then return "C" end
    if tool == "masking" then return "M" end
    return "D"
  end
  if name == nil or name == "" then return "?" end
  -- Other modules by full name, capitalised: "map" as a first letter collided
  -- with masking's "M" (measured 27 Sep). The board shows these verbatim.
  return string.upper(string.sub(name, 1, 1)) .. string.sub(name, 2)
end

-- Reads everything the board wants to know. Safe with no target photo.
local function readState()
  local s = { module = LrApplicationView.getCurrentModuleName() or "", tool = "" }
  if s.module == "develop" then
    LrTasks.pcall(function() s.tool = LrDevelopController.getSelectedTool() or "" end)
  end
  local catalog = LrApplication.activeCatalog()
  local photo = catalog:getTargetPhoto()
  if photo then
    s.id     = photo.localIdentifier or 0
    s.label  = string.lower(photo:getRawMetadata("colorNameForLabel") or "none")
    s.rating = photo:getRawMetadata("rating") or 0
    s.flag   = photo:getRawMetadata("pickStatus") or 0
  else
    s.id, s.label, s.rating, s.flag = 0, "none", 0, 0
  end
  if s.label == "" or s.label == "gray" or s.label == "grey" then s.label = "none" end
  return s
end

-- Strings that go inside the package's double quotes must contain no quote
-- or backslash, or the generated Lua breaks on the board.
local function clean(v)
  return (tostring(v or ""):gsub('[\\"]', ''))
end

-- Sends the state reply. Global so Start.lua's watcher can call it.
-- reason is for the log only. param/value are for drop (b); "" for now.
function LrcSendState(senderSocket, reason, param, value)
  LrTasks.startAsyncTask(function()
    local ok, err = LrTasks.pcall(function()
      local s = readState()
      if senderSocket == nil then
        -- Don't mark it sent: the watcher will retry once the link is back.
        logger:trace('REPLY ' .. reason .. ' NO SOCKET')
        return
      end
      last = s
      local json = string.format(
        '{"type":"active-photo-result","photo":{"id":%d,"isoSpeed":"%s","aperture":"%s","shutterSpeed":"%s","focalLength":"%s","rating":%d,"flag":%d}}',
        math.floor(s.id), moduleCode(s.module, s.tool), clean(s.label),
        clean(param), clean(value), math.floor(s.rating), math.floor(s.flag))
      senderSocket:send(json .. '\n')
      logger:trace('REPLY ' .. reason .. ' ' .. json)
    end)
    if not ok then
      logger:trace('REPLY ' .. tostring(reason) .. ' FAILED ' .. tostring(err))
    end
  end)
end

-- Polls for changes made outside the board. getSocket is a function because
-- Start.lua rebuilds the socket every time the link drops.
function LrcStartWatcher(getSocket, alive)
  LrTasks.startAsyncTask(function()
    logger:trace('WATCH start')
    while alive() do
      local ok, err = LrTasks.pcall(function()
        local socket = getSocket()
        if socket == nil then return end   -- link down: leave `last` alone, retry next tick
        local s = readState()
        if s.id ~= last.id or s.module ~= last.module or s.tool ~= last.tool
           or s.label ~= last.label or s.rating ~= last.rating or s.flag ~= last.flag then
          local reason = "meta"
          if s.module ~= last.module then reason = "module"
          elseif s.tool ~= last.tool then reason = "tool"
          elseif s.id ~= last.id then reason = "photo" end
          if s.id ~= last.id then turnStart = {} turnParam = nil snapValid = false end
          last = s
          LrcSendState(socket, reason)
        end
      end)
      if ok then
        LrTasks.sleep(0.3)
      else
        logger:trace('WATCH error ' .. tostring(err))
        LrTasks.sleep(3)
      end
    end
    logger:trace('WATCH stop')
  end)
end

-- --------------------------------------------------------------- echo ----

local LrDate = import 'LrDate'

-- Value formatting for the VALUE field: integers plain, else two decimals.
local function fmtValue(v)
  if v == nil then return "" end
  if math.floor(v) == v then return string.format("%d", v) end
  return (string.format("%.2f", v):gsub("0+$", ""):gsub("%.$", ""))
end

local pendingEcho = nil          -- { param = , value = } awaiting send

-- Parameters that live on a 0-360 circle: relative moves wrap, not clamp.
-- local_Hue is -100..100 in the SDK, not a circle; HSL hues are +-100 too.
local HUE_WRAP = {
  SplitToningShadowHue = true, SplitToningHighlightHue = true,
  ColorGradeMidtoneHue = true, ColorGradeGlobalHue = true,
}

-- Slider follow (0.2.9). Every parameter the board's pages know. Polled in
-- Develop; a value that changed without a board tick (mouse, keyboard,
-- preset, undo) is echoed with reason `follow`, and VSN1 selects its slot.
local WATCH = {
  "Temperature", "Tint", "Exposure", "Contrast", "Highlights", "Shadows",
  "Whites", "Blacks", "Texture", "Clarity", "Dehaze", "Vibrance", "Saturation",
  "PostCropVignetteAmount", "PostCropVignetteMidpoint",
  "Sharpness", "SharpenRadius", "SharpenDetail", "SharpenEdgeMasking",
  "LuminanceSmoothing", "LuminanceNoiseReductionDetail",
  "LuminanceNoiseReductionContrast", "ColorNoiseReduction",
  "ColorNoiseReductionDetail", "ColorNoiseReductionSmoothness",
  "GrainAmount", "GrainSize",
  "SplitToningShadowHue", "SplitToningShadowSaturation", "ColorGradeShadowLum",
  "SplitToningBalance", "ColorGradeMidtoneHue", "ColorGradeMidtoneSat",
  "ColorGradeMidtoneLum", "ColorGradeBlending", "SplitToningHighlightHue",
  "SplitToningHighlightSaturation", "ColorGradeHighlightLum",
  "ColorGradeGlobalLum", "ColorGradeGlobalHue", "ColorGradeGlobalSat",
  "ParametricHighlights", "ParametricLights", "ParametricDarks", "ParametricShadows",
  "local_Temperature", "local_Tint", "local_Exposure", "local_Contrast",
  "local_Highlights", "local_Shadows", "local_Whites", "local_Blacks",
  "local_Texture", "local_Clarity", "local_Dehaze", "local_Hue", "local_Saturation",
}

-- One pass over WATCH. Returns the first parameter whose value moved without
-- the board's doing, and its value; nil if none. The first pass after entering
-- Develop (or a photo change) only primes the snapshot.
local function followScan(force)
  if LrApplicationView.getCurrentModuleName() ~= "develop" then
    snapValid = false
    return nil
  end
  local found, foundValue = nil, nil
  for _, p in ipairs(WATCH) do
    local v = LrDevelopController.getValue(p)
    -- 0.2.13: a nil<->value change is a mask appearing or disappearing
    -- (every local_* flips nil<->0 on mask enter/exit/create — measured
    -- 1 Oct, 952 stray follows on local_Temperature). Not a slider move.
    if snapValid and not force and v ~= snap[p] and found == nil
       and v ~= nil and snap[p] ~= nil then
      found, foundValue = p, v
    end
    snap[p] = v
  end
  snapValid = true
  return found, foundValue
end

-- Called from the develop handler (socket callback, no yielding here).
-- A turn starts at the first tick on a parameter and ends only on
-- revert-param / reset-param for it, or a change of photo — NOT on a pause
-- (0.2.8; the 0.5 s gap rule reverted to wherever the last fiddle began).
-- 0.2.9: only ONE turn exists at a time — a tick on a different parameter
-- starts a new turn there (switching sliders sets the reset point).
local function noteTick(param, valueBefore, valueAfter)
  if turnParam ~= param then
    turnStart = {}
    turnParam = param
    turnStart[param] = valueBefore
  end
  snap[param] = valueAfter   -- the board did this: not a mouse change
  pendingEcho = { param = param, value = valueAfter }
end

-- Drains pendingEcho at most twenty times a second (0.2.14; was ten); the last tick of a turn is
-- always sent because nothing clears pendingEcho except this task.
function LrcStartEcho(getSocket, alive)
  LrTasks.startAsyncTask(function()
    logger:trace('ECHO start')
    while alive() do
      local ok, err = LrTasks.pcall(function()
        local socket = getSocket()
        if socket ~= nil and pendingEcho ~= nil then
          local e = pendingEcho
          pendingEcho = nil
          LrcSendState(socket, "echo", e.param, fmtValue(e.value))
        elseif socket ~= nil then
          scanTick = (scanTick or 0) + 1
          if scanTick % 4 == 0 then   -- 0.2.14: echo loop at 0.05 s, follow scan held at 5 Hz
            local p, v = followScan(false)
            if p then LrcSendState(socket, "follow", p, fmtValue(v)) end
          end
        end
      end)
      if ok then
        LrTasks.sleep(0.05)   -- 0.2.14: was 0.1; LCD/VSN2 readout lag (session log item 3)
      else
        logger:trace('ECHO error ' .. tostring(err))
        LrTasks.sleep(3)
      end
    end
    logger:trace('ECHO stop')
  end)
end

-- ----------------------------------------------------------- commands ----

local function photoTableToJsonArray(tbl)
  local jsonStr = "["
  local first = true
  for _, obj in ipairs(tbl) do
      if not first then
          jsonStr = jsonStr .. ","
      end
      first = false
      jsonStr = jsonStr .. string.format('{"id":%d,"name":"%s"}', obj.id, obj.name)
  end
  jsonStr = jsonStr .. "]"
  return jsonStr
end

function handleMessage(message, senderSocket)
  local command = message:match("^(.-),")
  if command == nil then
    command = message
  end
  if (message:match("^1") ~= nil) then -- ping message
    return
  end
  logger:trace('COMMAND ' .. command)
  if command == "rating" then
    local ratingValue = message:match("^rating,%s*(.*)")
    if ratingValue == "+1" then
      LrSelection.increaseRating()
    elseif ratingValue == "-1" then
      LrSelection.decreaseRating()
    else
      LrSelection.setRating(ratingValue)
    end
    LrcSendState(senderSocket, "rating")
  elseif command == "flag" then
    local flagValue = message:match("^flag,%s*(.*)")
    if flagValue == "pick" then
      LrSelection.flagAsPick()
    elseif flagValue == "reject" then
      LrSelection.flagAsReject()
    elseif flagValue == "remove" then
      LrSelection.removeFlag()
    end
    LrcSendState(senderSocket, "flag")
  elseif command == "color" then
    local colorValue = message:match("^color,%s*(.*)")
    LrSelection.setColorLabel(colorValue)
    LrcSendState(senderSocket, "color")
  elseif command == "color-toggle" then
    -- Same colour again clears it: press green on a green photo -> none.
    local colorValue = string.lower(message:match("^color%-toggle,%s*(.*)") or "")
    LrTasks.startAsyncTask(function()
      local ok, err = LrTasks.pcall(function()
        local s = readState()
        if s.label == colorValue then
          LrSelection.setColorLabel("none")
        else
          LrSelection.setColorLabel(colorValue)
        end
      end)
      if not ok then logger:trace('COLOR-TOGGLE FAILED ' .. tostring(err)) end
      LrcSendState(senderSocket, "color-toggle")
    end)
  elseif command == "state" then
    LrcSendState(senderSocket, "state")
  elseif command == "next-photo" then
    LrSelection.nextPhoto()
    LrcSendState(senderSocket, "next")
  elseif command == "previous-photo" then
    LrSelection.previousPhoto()
    LrcSendState(senderSocket, "prev")
  elseif command == "develop" then
    local parameterName, parameterValue, isRelative = message:match("^develop,%s*(.*),%s*(.*),%s*(.*)")
    LrDevelopController.startTracking(parameterName)
    LrApplicationView.switchToModule("develop")
    local nextValue = tonumber(parameterValue)
    local currentValue = LrDevelopController.getValue(parameterName)
    if isRelative == "1" then
      nextValue = nextValue + currentValue
      -- 0.2.11: hue is a circle. setValue clamps at 0 and 360 (measured 1 Oct:
      -- the jog jammed at both ends), so wrap relative moves on the hue
      -- parameters. Lua's % is floored: -5 % 360 == 355.
      if HUE_WRAP[parameterName] then nextValue = nextValue % 360 end
    end
    LrDevelopController.setValue(parameterName, tonumber(nextValue))
    local afterValue = LrDevelopController.getValue(parameterName)
    -- 0.2.17 (20 Nov): one line per develop command, so a jump identifies
    -- itself: the raw message as received, LrC's value before, what the
    -- plugin asked for, and what LrC ended up with.
    logger:trace('DEV [' .. message .. '] before=' .. tostring(currentValue)
      .. ' asked=' .. tostring(nextValue) .. ' after=' .. tostring(afterValue))
    noteTick(parameterName, currentValue, afterValue)
  elseif command == "preset" then
    -- 0.2.15: split-tone preset as ONE message — shadow hue, shadow sat,
    -- highlight hue, highlight sat — so the four never race each other or
    -- anything else through the package's 50 ms drain. Echoes both
    -- saturations for the VSN1 LCD.
    local sh, ss, hh, hs = message:match("^preset,%s*([%-%d%.]+),%s*([%-%d%.]+),%s*([%-%d%.]+),%s*([%-%d%.]+)")
    LrTasks.startAsyncTask(function()
      local vals = { { "SplitToningShadowHue", tonumber(sh) }, { "SplitToningShadowSaturation", tonumber(ss) },
                     { "SplitToningHighlightHue", tonumber(hh) }, { "SplitToningHighlightSaturation", tonumber(hs) } }
      local ok, err = LrTasks.pcall(function()
        LrApplicationView.switchToModule("develop")
        for _, pv in ipairs(vals) do
          if pv[2] ~= nil then
            LrDevelopController.startTracking(pv[1])
            LrDevelopController.setValue(pv[1], pv[2])
            snap[pv[1]] = pv[2]
          end
        end
      end)
      logger:trace('PRESET ' .. tostring(sh) .. ',' .. tostring(ss) .. ',' .. tostring(hh) .. ',' .. tostring(hs) .. ' ' .. tostring(ok) .. ' ' .. tostring(err))
      LrcSendState(senderSocket, "preset", "SplitToningShadowSaturation", fmtValue(tonumber(ss)))
      LrcSendState(senderSocket, "preset", "SplitToningHighlightSaturation", fmtValue(tonumber(hs)))
    end)
  elseif command == "reset-param" then
    -- One parameter to Adobe's default, then echo the result.
    local parameterName = message:match("^reset%-param,%s*(.*)")
    LrTasks.startAsyncTask(function()
      local ok, err = LrTasks.pcall(function()
        LrDevelopController.resetToDefault(parameterName)
      end)
      logger:trace('RESET-PARAM ' .. tostring(parameterName) .. ' ' .. tostring(ok) .. ' ' .. tostring(err))
      local v = nil
      LrTasks.pcall(function() v = LrDevelopController.getValue(parameterName) end)
      turnStart[parameterName] = nil
      if v ~= nil then snap[parameterName] = v end
      LrcSendState(senderSocket, "reset", parameterName, fmtValue(v))
    end)
  elseif command == "revert-param" then
    -- Back to where the parameter was before the current turn started.
    local parameterName = message:match("^revert%-param,%s*(.*)")
    LrTasks.startAsyncTask(function()
      local v = turnStart[parameterName]
      if v == nil then
        logger:trace('REVERT-PARAM ' .. tostring(parameterName) .. ' nothing to revert to')
        return
      end
      local ok, err = LrTasks.pcall(function()
        LrDevelopController.setValue(parameterName, v)
      end)
      logger:trace('REVERT-PARAM ' .. tostring(parameterName) .. ' -> ' .. tostring(v) .. ' ' .. tostring(ok) .. ' ' .. tostring(err))
      turnStart[parameterName] = nil
      snap[parameterName] = v
      LrcSendState(senderSocket, "revert", parameterName, fmtValue(v))
    end)
  elseif command == "develop-range" then
    local parameterName = message:match("^develop%-range,%s*(.*)")
    local rangeMin, rangeMax = LrDevelopController.getRange(parameterName)
    senderSocket:send('{"type":"range-result","name":"' .. parameterName .. '","min":' .. rangeMin .. ',"max":' .. rangeMax .. '}\n')
  elseif command == "remove" then
    local parameterName, parameterValue = message:match("^remove,%s*(.*),%s*(.*)")
    if parameterName == "size" then
      local params = {
        brushSize = tonumber(parameterValue)
      }
      logger:trace('TABLE ' .. params.brushSize)
      LrTasks.startAsyncTask(function()
      local result, error = LrDevelopController.setRemovePanelPreferences(params)
      end)
    elseif parameterName == "feather" then
      local params = {
        brushFeather = tonumber(parameterValue)
      }
      logger:trace('TABLE2 ' .. params.brushFeather)

    LrTasks.startAsyncTask(function()
      LrDevelopController.setRemovePanelPreferences(params)
    end)
    end
  elseif command == "undo" then
    LrUndo.undo()
    LrcSendState(senderSocket, "undo")
  elseif command == "redo" then
    LrUndo.redo()
    LrcSendState(senderSocket, "redo")
  elseif command == "create-virtual" then
    LrApplication.activeCatalog():createVirtualCopies()
  elseif command == "view" then
    local viewValue = message:match("^view,%s*(.*)")
    if viewValue == "library" then
      -- One key for E and G: from another module go to Library (Loupe);
      -- inside Library alternate Loupe <-> Grid. The SDK has no view getter
      -- and toggleLoupe() flips against the PREVIOUS view (measured: from
      -- Survey it gave Loupe<->Survey), so the plugin remembers the last view
      -- it set itself. A view changed from the keyboard is not seen; the
      -- next press corrects it. (Drop c.1, 27 Sep.)
      LrTasks.startAsyncTask(function()
        local ok, err = LrTasks.pcall(function()
          if LrApplicationView.getCurrentModuleName() ~= "library" then
            -- Leaving Develop means the image is done or another is wanted:
            -- Grid, never Loupe.
            LrApplicationView.switchToModule("library")
            LrApplicationView.showView("grid")
            lastView = "grid"
          elseif lastView == "grid" then
            LrApplicationView.showView("loupe")
            lastView = "loupe"
          else
            -- From Loupe, Survey, Compare or anything else: Grid.
            LrApplicationView.showView("grid")
            lastView = "grid"
          end
        end)
        if not ok then logger:trace('VIEW library FAILED ' .. tostring(err)) end
      end)
    else
      lastView = viewValue
      LrApplicationView.showView(viewValue)
    end
  elseif command == "zoom-toggle" then
    LrApplicationView.toggleZoom()
  elseif command == "zoom-in" then
    LrApplicationView.zoomIn()
  elseif command == "zoom-out" then
    LrApplicationView.zoomOut()
  elseif command == "zoom-onetoone" then
    LrApplicationView.zoomToOneToOne()
  elseif command == "copy" then
    local catalog = LrApplication.activeCatalog()
    local photo = catalog:getTargetPhoto()
    photo:copySettings()
  elseif command == "paste" then
    local catalog = LrApplication.activeCatalog()
    local photo = catalog:getTargetPhoto()
    photo:pasteSettings()
  elseif command == "reset" then
    LrDevelopController.resetAllDevelopAdjustments()
  elseif command == "selectall" then
    LrSelection.selectAll()
  elseif command == "goto-remove" then
    LrDevelopController.goToRemove()
  elseif command == "goto-mask" or command == "goto-crop" or command == "select-tool" or command == "tool-toggle" then
    -- Stock code called selectTool bare; a failure there vanished into the
    -- socket callback. 0.2.6: logged (measured working for "masking").
    -- 0.2.7: "select-tool,<name>" for any tool ("loupe" leaves the current
    -- one — the Mask hold's release edge), and "tool-toggle,<name>": that
    -- tool if another is selected, else back to loupe (BU16's press keys).
    local tool
    if command == "goto-mask" then tool = "masking"
    elseif command == "goto-crop" then tool = "crop"
    else tool = message:match("^[%w%-]+,%s*(.*)") end
    LrTasks.startAsyncTask(function()
      local ok, err = LrTasks.pcall(function()
        if command == "tool-toggle" and LrDevelopController.getSelectedTool() == tool then
          tool = "loupe"
        end
        LrDevelopController.selectTool(tool)
      end)
      logger:trace('SELECT-TOOL ' .. tostring(tool) .. ' ' .. tostring(ok) .. ' ' .. tostring(err))
    end)
  elseif command == "photos-name" then
    LrTasks.startAsyncTask(function()
      local catalog = LrApplication.activeCatalog()
      local photos = catalog:getAllPhotos()
      local returnValue = {}
      for _, photo in ipairs(photos) do
        table.insert(returnValue, { id = photo.localIdentifier, name = photo:getFormattedMetadata("fileName") })
      end
      local jsonResult = photoTableToJsonArray(returnValue)
      senderSocket:send('{"type":"photos-name-result","result":'.. jsonResult .. '}\n')
      LrcSendState(senderSocket, "photos-name")
    end)
  end
end
