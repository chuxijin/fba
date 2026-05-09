import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  input: './openapi.json',
  output: {
    path: './src/generated',
    format: 'prettier',
    lint: false,
  },
  plugins: [
    {
      name: '@hey-api/client-axios',
      runtimeConfigPath: './src/runtime/axios.ts',
    },
    {
      name: '@hey-api/sdk',
      asClass: false,
    },
    {
      name: '@hey-api/typescript',
      enums: 'typescript',
    },
  ],
});
