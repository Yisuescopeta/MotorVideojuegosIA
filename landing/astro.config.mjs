import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
  site: 'https://yisuescopeta.github.io',
  base: '/MotorVideojuegosIA',
  output: 'static',
  build: {
    inlineStylesheets: 'auto',
  },
});