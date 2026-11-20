-- LR Console — forked Lightroom plugin for the Intech Grid "Lightroom Classic"
-- package. Drop (a), 27 Sep 2026.
--
-- Forked from Intech Studio's Grid Editor plugin (com.intechstudio.grideditor).
-- Own identifier so both can be installed, but ONLY ONE may be enabled at a
-- time: both listen on 127.0.0.1:23111 for the Grid Editor package.
return {
  VERSION = { major = 0, minor = 2, revision = 17, },
  LrSdkVersion = 6.0,
  LrSdkMinimumVersion = 6.0,
  LrToolkitIdentifier = "com.selbyspink.lrconsole",
  LrPluginName = "LR Console (Grid fork)",
  LrInitPlugin = "Start.lua",
  LrForceInitPlugin = true,
  LrShutdownApp = "Shutdown.lua",
  LrDisablePlugin = "Stop.lua",
  LrHelpMenuItems = {
    { title = 'About LR Console', file = 'MenuItemAbout.lua' },
  },
  LrExportMenuItems = {
    { title = "LR Console: Start", file = "Start.lua" },
    { title = "LR Console: Stop",  file = "Stop.lua"  },
  },
}
