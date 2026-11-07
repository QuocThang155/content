import { defineConfig, globalIgnores } from 'eslint/config';
import nextConfig from 'eslint-config-next/core-web-vitals';
import nextTypescriptConfig from 'eslint-config-next/typescript';

export default defineConfig([
  ...nextConfig,
  ...nextTypescriptConfig,
  globalIgnores([
    '.next/**',
    'node_modules/**',
    'next-env.d.ts',
  ]),
]);
