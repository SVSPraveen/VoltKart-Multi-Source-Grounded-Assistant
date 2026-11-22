const fs = require('fs');
const path = require('path');

const target = path.join(__dirname, 'node_modules', 'rollup', 'dist', 'native.js');
if (fs.existsSync(target)) {
  let content = fs.readFileSync(target, 'utf8');
  if (!content.includes('@rollup/wasm-node')) {
    content = content.replace(
      'const nativeModule = requireWithFriendlyError(',
      `let nativeModule;\ntry {\n  nativeModule = requireWithFriendlyError(`
    ).replace(
      ');\n\nconst { parse, parseAsync',
      `);\n} catch (e) {\n  try {\n    nativeModule = require('@rollup/wasm-node/dist/native.js');\n  } catch (e2) {\n    throw e;\n  }\n}\n\nconst { parse, parseAsync`
    );
    fs.writeFileSync(target, content, 'utf8');
    console.log('Successfully patched rollup for WASM fallback.');
  }
}
