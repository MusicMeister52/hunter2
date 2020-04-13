const { merge } = require('webpack-merge')
const common = require('./webpack.common.js')
const { BundleAnalyzerPlugin } = require('webpack-bundle-analyzer')

const DEV_SERVER_HOST = process.env.H2_WEBPACK_DEV_HOST || 'localhost'
const DEV_SERVER_PORT = parseInt(process.env.H2_WEBPACK_DEV_PORT, 10) || 4000
const PUBLIC_PATH     = `http://${DEV_SERVER_HOST}:${DEV_SERVER_PORT}/assets/bundles/`

module.exports = merge(common, {
  mode: 'development',
  devtool: 'source-map',

  output: {
    devtoolNamespace: 'hunter2',
    publicPath: PUBLIC_PATH,
  },

  devServer: {
    publicPath: PUBLIC_PATH,
    host: '0.0.0.0',
    port: DEV_SERVER_PORT,
    disableHostCheck: true,
    headers: {
      'Access-Control-Allow-Origin': '*',
    },
  },

  plugins: [
    new BundleAnalyzerPlugin({
      analyzerHost: '0.0.0.0',
    }),
  ],

  resolve: {
    alias: {
      'vue$': 'vue/dist/vue.esm.js',
    },
  },

  watchOptions: {
    aggregateTimeout: 300,
    poll: 1000,
  },
})
