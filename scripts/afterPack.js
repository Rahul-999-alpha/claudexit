const path = require('path')
const { rcedit } = require('rcedit')

exports.default = async function afterPack(context) {
  if (process.platform !== 'win32') return

  const exeName = `${context.packager.appInfo.productFilename}.exe`
  const exePath = path.join(context.appOutDir, exeName)
  const iconPath = path.resolve(__dirname, '../build/icon.ico')
  const version = context.packager.appInfo.version

  console.log(`[afterPack] Patching ${exeName} — icon + version ${version}`)

  await rcedit(exePath, {
    icon: iconPath,
    'file-version': version,
    'product-version': version,
    'version-string': {
      ProductName: 'claudexit',
      FileDescription: 'claudexit — Claude Desktop Exporter',
      CompanyName: 'Rahul Daswani',
      LegalCopyright: `Copyright ${new Date().getFullYear()} Rahul Daswani`,
      OriginalFilename: exeName
    }
  })

  console.log('[afterPack] Done')
}
