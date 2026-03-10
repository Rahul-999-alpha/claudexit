// afterPack hook for electron-builder
// Embeds version info and icon into the exe

exports.default = async function (context) {
  console.log(`[afterPack] Platform: ${context.electronPlatformName}`)
  console.log(`[afterPack] App: ${context.appOutDir}`)
}
