import { defineConfig } from 'tsup';

export default defineConfig({
  entry: {
    index: 'src/index.ts',
    'runtime/index': 'src/runtime/index.ts',
    'generated/index': 'src/generated/index.ts',
    'plugins/index': 'src/plugins/index.ts',
    'typed/index': 'src/typed/index.ts',
  },
  format: ['esm', 'cjs'],
  dts: true,
  clean: true,
  splitting: true,
  sourcemap: true,
  treeshake: true,
  outDir: 'dist',
  target: 'es2022',
});
