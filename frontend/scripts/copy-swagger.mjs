import {mkdir, copyFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import path from 'node:path';
const require = createRequire(import.meta.url);
const source = path.dirname(require.resolve('swagger-ui-dist/package.json'));
await mkdir('dist/swagger', {recursive: true});
for (const name of ['swagger-ui-bundle.js', 'swagger-ui.css']) {
  await copyFile(path.join(source, name), path.join('dist/swagger', name));
}
