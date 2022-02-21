module.exports = {
  'env': {
    'browser': true,
    'es2022': true,
  },
  'extends': [
    'eslint:recommended',
    'plugin:vue/vue3-recommended',
  ],
  'globals': {
    'Atomics': 'readonly',
    'SharedArrayBuffer': 'readonly',
  },
  'parserOptions': {
    'sourceType': 'module',
  },
  'overrides': [
    {
      'env': {
        'node': true,
      },
      'files': [
        'postcss.config.js',
        'webpack.*.js',
      ],
    },
  ],
  'rules': {
    'comma-dangle': [
      'error',
      'always-multiline',
    ],
    'indent': [
      'error',
      2,
    ],
    'linebreak-style': [
      'error',
      'unix',
    ],
    'quotes': [
      'error',
      'single',
    ],
    'semi': [
      'error',
      'never',
    ],
    'strict': [
      'error',
    ],
  },
}
