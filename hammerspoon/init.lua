-- Bring Lightroom Classic to the front when the board's "LrC" key types
-- Ctrl+Opt+Cmd+L. Add to ~/.hammerspoon/init.lua and reload Hammerspoon.
-- (The Grid can type keystrokes but can't switch apps; this bridges it.)
hs.hotkey.bind({"ctrl", "alt", "cmd"}, "L", function()
  hs.application.launchOrFocus("Adobe Lightroom Classic")
end)
