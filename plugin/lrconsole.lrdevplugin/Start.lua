-- LR Console fork — Start.lua — drop (b), 27 Sep 2026.
-- Stock socket code, verbatim, plus: separate log name, and the watcher task
-- started once the run loop is up (see ProcessMessage.lua).

local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'

local LrSocket = import "LrSocket"
local LrLogger = import 'LrLogger'
local LrDate = import 'LrDate'
local LrFunctionContext = import "LrFunctionContext"
local logger = LrLogger('LRConsole')
logger:enable("logfile")
logger:trace('LR Console fork 0.2.16 starting')

require 'ProcessMessage'

-- 0.2.16: ask LrC to expand the panel of any slider the board moves
-- (experiment, [stated 2 Oct]; interaction with Solo Mode unknown). The
-- call needs the Develop module, so it is retried until it takes.
LrTasks.startAsyncTask(function()
  local LrDevelopController = import 'LrDevelopController'
  local LrApplicationView = import 'LrApplicationView'
  for i = 1, 600 do
    if LrApplicationView.getCurrentModuleName() == "develop" then
      local ok, err = LrTasks.pcall(function() LrDevelopController.revealAdjustedControls(true) end)
      logger:trace('REVEAL-ADJUSTED ' .. tostring(ok) .. ' ' .. tostring(err))
      if ok then return end
    end
    LrTasks.sleep(1)
  end
  logger:trace('REVEAL-ADJUSTED gave up (never in Develop)')
end)

local receiverSocket
local receiverPort = 0
local receiverConnected = false

local senderSocket
local senderPort = 23111
local senderConnected = false
local senderErrors = 0

local lastReceivedMessageTime = 0

local function createReceiverSocket(context)
  if receiverSocket ~= nil then
    return
  end
  logger:trace('Creating receiver socket')
  receiverPort = 0
  receiverSocket = LrSocket.bind
  {
    functionContext = context,
    address = "127.0.0.1",
    port = 0,
    mode = "receive",
    plugin = _PLUGIN,
    onConnecting = function(socket, port)
      logger:trace('Receiver socket connecting: ' .. port)
      receiverPort = port
      if senderConnected then
        senderSocket:send('{"type":"receiver-port","port":'.. receiverPort .. '}\n')
      end
    end,
    onConnected = function(socket, port)
      logger:trace('Receiver socket connected: ' .. port)
      receiverConnected = true
    end,
    onClosed = function(socket)
      logger:trace('Receiver socket closed: ' .. receiverPort)
      receiverConnected = false
      receiverPort = 0
    end,
    onError = function(socket, err)
      receiverConnected = false
      socket:reconnect()
      logger:trace('Receiver socket %d error: %s', receiverPort, err)
    end,

    onMessage = function(socket, message)
      lastReceivedMessageTime = LrDate.currentTime()
      handleMessage(message, senderSocket)
    end,
  }
  return
end

local function createSenderSocket(context)
  if senderSocket ~= nil then
    return
  end
  logger:trace("Creating sender socket")

  senderSocket = LrSocket.bind
  {
      functionContext = context,
      port = senderPort,
      mode = "send",
      plugin = _PLUGIN,
      onConnecting = function(socket, port)
        logger:trace('Sender socket connecting: ' .. port)
      end,
      onConnected = function(socket, port)
        logger:trace('Sender socket connected: ' .. port .. ' after ' .. senderErrors .. ' errors')
        senderErrors = 0
        senderConnected = true
        lastReceivedMessageTime = LrDate.currentTime()
        if receiverPort ~= 0 then
          senderSocket:send('{"type":"receiver-port","port":'.. receiverPort .. '}\n')
        end
      end,
      onClosed = function(socket)
        logger:trace('Sender socket closed: ' .. senderPort)
        senderConnected = false
      end,
      onError = function(socket, err)
        senderErrors = senderErrors + 1
        if senderErrors == 1 or senderErrors % 200 == 0 then
          logger:trace('Sender socket ' .. senderPort .. ' error (' .. senderErrors .. ' so far): ' .. tostring(err))
        end
        senderConnected = false
        socket:reconnect()
      end,
  }
  return senderSocket
end

-- Plug-in reload starts this file again in a FRESH Lua environment: the
-- previous instance keeps its own _G, loops and sockets, and this handoff
-- never sees it (measured 27 Sep: 200/s "failed to open 23111" while the
-- old code kept serving). So a plugin update needs a Lightroom restart. The
-- handoff below is kept only for the case where LrC ever reuses the state.
_G.lrcGen = (_G.lrcGen or 0) + 1
local myGen = _G.lrcGen

local function alive()
  return _G.running and _G.lrcGen == myGen
end

LrTasks.startAsyncTask(function()
  if _G.running then
    logger:trace('Previous instance running; asking it to stop')
    _G.shutdown = false
    _G.running = false
    local waited = 0
    while not _G.shutdown and waited < 6 do
      LrTasks.sleep(0.1)
      waited = waited + 0.1
    end
    logger:trace('Previous instance ' .. (_G.shutdown and 'stopped' or 'did not stop in time'))
  end
  _G.shutdown = false
  LrFunctionContext.callWithContext('lrconsole', function(context)
    _G.running = true
    -- The watcher only sends when the sender socket is connected; otherwise
    -- it logs NO SOCKET and the next change after reconnection catches up.
    local getSocket = function()
      if senderConnected then return senderSocket end
      return nil
    end
    LrcStartWatcher(getSocket, alive)
    LrcStartEcho(getSocket, alive)
    while alive() do
      createReceiverSocket(context)
      createSenderSocket(context)
      while alive() and ((not senderConnected) or (LrDate.currentTime() - lastReceivedMessageTime) < 5) do
        LrTasks.sleep(0.5)
      end
      receiverSocket:close()
      senderSocket:close()
      receiverSocket = nil
      senderSocket = nil
      senderConnected = false
      receiverConnected = false
    end
    _G.shutdown = true
  end)
end)
