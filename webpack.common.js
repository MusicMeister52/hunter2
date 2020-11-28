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
    hunts_admin_progress:    'hunts/js/admin/progress-entrypoint.js',
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
        test: /\.(png|jpg|jpeg|gif|eot|ttf|woff|woff2|svg|svgz)(\?.+)?$/,
        use: [
          {
            loader: 'file-loader',
          },
        ],
      },
      {
        test: /\.m?js$/,
        exclude: /node_modules\/(?!bootstrap-vue\/src\/)/,
        use: {
          loader: 'babel-loader',
          options: {
            cacheDirectory: '/var/cache/babel-loader',
            presets: [['@babel/preset-env', { 'targets': 'defaults' }]],
            plugins: [
              [
                'component',
                {
                  'libraryName': 'element-ui',
                  'styleLibraryName': 'theme-chalk',
                },
              ],
            ],
          },
        },
      },
      {
        test: /\.vue$/,
        use: [
          'vue-loader',
        ],
      },
      {
        test: /\.s?css$/,
        use: [
          MiniCssExtractPlugin.loader,
          'css-loader',
          'postcss-loader',
          'sass-loader',
        ],
      },
    ],
  },

  output: {
    path: path.resolve('../assets/bundles/'),
    filename: '[name]/[contenthash].js',
    libraryTarget: 'var',
    library: '[name]',
  },

  plugins: [
    new BundleTracker({filename: './webpack-stats.json'}), // Required for django-webpack-loader
    new MiniCssExtractPlugin({
      filename: '[name]/[contenthash].css',
    }),
    new VueLoaderPlugin(),
  ],

  resolve: {
    alias: {
      // Alias for using source of BootstrapVue
      'bootstrap-vue$': 'bootstrap-vue/src/index.js',
    },
    modules: [
      path.resolve('.'),
      path.resolve('../node_modules'),
    ],
  },
}
