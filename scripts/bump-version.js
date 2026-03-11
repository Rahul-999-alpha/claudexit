/**
 * Centralized version bump script.
 * Usage: node scripts/bump-version.js <version>
 *   or:  npm run version:bump <version>
 *
 * Updates:
 *   - package.json          → "version": "<version>"
 *   - backend/app/main.py   → version="<version>"
 */

const fs = require('fs')
const path = require('path')

const version = process.argv[2]
if (!version || !/^\d+\.\d+\.\d+/.test(version)) {
  console.error('Usage: node scripts/bump-version.js <version>  (e.g. 1.2.0)')
  process.exit(1)
}

const root = path.resolve(__dirname, '..')

// 1. package.json
const pkgPath = path.join(root, 'package.json')
const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'))
const oldVersion = pkg.version
pkg.version = version
fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n')
console.log(`  package.json: ${oldVersion} → ${version}`)

// 2. backend/app/main.py
const mainPyPath = path.join(root, 'backend', 'app', 'main.py')
let mainPy = fs.readFileSync(mainPyPath, 'utf-8')
mainPy = mainPy.replace(/version="[^"]+"/, `version="${version}"`)
fs.writeFileSync(mainPyPath, mainPy)
console.log(`  backend/app/main.py: → ${version}`)

console.log(`\n  ✓ Bumped to v${version}`)
