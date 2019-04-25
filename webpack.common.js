const path = require('path')
const BundleTracker = require('webpack-bundle-tracker')
const MiniCssExtractPlugin = require('mini-css-extract-plugin')
const VueLoaderPlugin = require('vue-loader/lib/plugin')

module.exports = {
  context: '/usr/src/app',

  entry: {
    sentry:             'hunter2/js/sentry.js',
    hunter2:            'hunter2/js/index.js',
    teams_manage:       'teams/js/manage.js',
    hunts_event:        'hunts/js/event.js',
    hunts_admin_puzzle: 'imports-loader?$=jquery!hunts/js/admin_puzzle.js',
    hunts_puzzle:       'hunts/js/puzzle.js',
    hunts_about:        'hunts/scss/about.scss',
    hunts_stats:        'hunts/js/stats.js',
    hunts_guesses:      'hunts/js/guesses.js',
  },

  module: {
    rules: [
      {
        test: /\.vue$/,
        use: [
          'vue-loader?sourceMap',
        ],
      },
      {
        test: /\.scss$/,
        use: [
          MiniCssExtractPlugin.loader,
          'css-loader?sourceMap',
          'postcss-loader?sourceMap',
          'sass-loader?sourceMap',
        ],
      },
    ],
  },

  output: {
    path: path.resolve('assets/bundles/'),
    filename: '[name]/[hash].js',
    libraryTarget: 'var',
    library: '[name]',
  },

  plugins: [
    new BundleTracker({filename: './webpack-stats.json'}), // Required for django-webpack-loader
    new MiniCssExtractPlugin({
      filename: '[name]/[hash].css',
    }),
    new VueLoaderPlugin(),
  ],

  resolve: {
    modules: [
      path.resolve('.'),
      path.resolve('./node_modules'),
    ],
  },
}
