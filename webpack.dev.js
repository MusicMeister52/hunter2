const merge = require('webpack-merge')
const common = require('./webpack.common.js')

const DEV_SERVER_HOST = process.env.H2_WEBPACK_DEV_HOST || 'localhost'
const DEV_SERVER_PORT = parseInt(process.env.H2_WEBPACK_DEV_PORT, 10) || 4000

module.exports = merge(common, {
  mode: 'development',
  devtool: 'source-map',

  output: {
    publicPath: `http://${DEV_SERVER_HOST}:${DEV_SERVER_PORT}/assets/bundles/`,
  },

  devServer: {
    host: '0.0.0.0',
    port: DEV_SERVER_PORT,
    disableHostCheck: true,
  },

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
