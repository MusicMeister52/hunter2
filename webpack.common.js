const path = require('path')
const BundleTracker = require('webpack-bundle-tracker')
const MiniCssExtractPlugin = require('mini-css-extract-plugin')
const VueLoaderPlugin = require('vue-loader/lib/plugin')

module.exports = {
  context: '/opt/hunter2/src',

  entry: {
    sentry:                  'hunter2/js/sentry.js',
    hunter2:                 'hunter2/js/index.js',
    accounts_profile:        'accounts/scss/profile.scss',
    hunts_admin_crud_puzzle: 'imports-loader?imports=default|jquery|$!hunts/js/admin/crud/puzzle.js',
    hunts_admin_guesses:     'hunts/js/admin/guesses.js',
    hunts_admin_stats:       'hunts/js/admin/stats.js',
    hunts_admin_team:        'hunts/js/team-admin-entrypoint.js',
    hunts_about:             'hunts/scss/about.scss',
    hunts_event:             'hunts/js/event.js',
    hunts_puzzle:            'hunts/js/puzzle.js',
    teams_manage:            'teams/js/manage.js',
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
          {
            loader: MiniCssExtractPlugin.loader,
            options: {
              esModule: true,
            },
          },
          'css-loader?sourceMap',
          'postcss-loader?sourceMap',
          'sass-loader?sourceMap',
        ],
      },
    ],
  },

  output: {
    path: path.resolve('../assets/bundles/'),
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
      path.resolve('../node_modules'),
    ],
  },
}
