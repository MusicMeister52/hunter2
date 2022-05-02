const path = require('path')
const AutoImport = require('unplugin-auto-import/webpack')
const BundleTracker = require('webpack-bundle-tracker')
const Components = require('unplugin-vue-components/webpack')
const CssMinimizerPlugin = require('css-minimizer-webpack-plugin')
const { DefinePlugin } = require('webpack')
const MiniCssExtractPlugin = require('mini-css-extract-plugin')
const { VueLoaderPlugin } = require('vue-loader')
const { ElementPlusResolver } = require('unplugin-vue-components/resolvers')

module.exports = {
  context: '/opt/hunter2/src',
  devtool: 'source-map',

  entry: {
    sentry: 'hunter2/js/sentry.js',
    hunter2: 'hunter2/js/index.js',
    accounts_profile: 'accounts/scss/profile.scss',
    hunts_admin_crud_puzzle: 'imports-loader?imports=default|jquery|$!hunts/js/admin/crud/puzzle.js',
    hunts_admin_guesses: 'hunts/js/admin/guesses.js',
    hunts_admin_progress: 'hunts/js/admin/progress-entrypoint.js',
    hunts_admin_stats: 'hunts/js/admin/stats.js',
    hunts_admin_team: 'hunts/js/admin/team-entrypoint.js',
    hunts_admin_reset_progress: 'hunts/scss/admin/reset_progress.scss',
    hunts_about: 'hunts/scss/about.scss',
    hunts_event: 'hunts/js/event.js',
    hunts_puzzle: 'hunts/js/puzzle.js',
    hunts_stats: 'hunts/js/stats.js',
    hunts_stats_progress: 'hunts/stats/js/progress.js',
    hunts_stats_distributions: 'hunts/stats/js/solve_time_distributions.js',
    teams_manage: 'teams/js/manage.js',
  },

  externals: {
    moment: 'moment',  // We don't want to let moment end up in our bundles
  },

  module: {
    rules: [
      {
        test: /\.(png|jpe?g|gif|eot|ttf|woff2?|svgz?)(\?.+)?$/,
        type: 'asset',
      },
      {
        test: /\.m?js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            cacheDirectory: '/var/cache/babel-loader',
            presets: [['@babel/preset-env', { 'targets': 'defaults' }]],
            plugins: [
              'component',
            ],
          },
        },
      },
      {
        test: /\.mjs$/,
        resolve: {
          fullySpecified: false,
        },
        include: /node_modules/,
        type: 'javascript/auto',
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

  optimization: {
    minimizer: [
      '...',
      new CssMinimizerPlugin(),
    ],
    splitChunks: {
      chunks: (chunk) => {
        // Running splitChunks on 'hunts_stats_distributions' somehow results in the following bug:
        // Uncaught TypeError: o.nL is undefined
        // solve_time_distributions.js:30:2
        return chunk.name !== 'hunts_stats_distributions'
      },
    },
  },

  output: {
    devtoolNamespace: 'hunter2',
    path: path.resolve('../assets/bundles/'),
    filename: '[name]/[contenthash].js',
    libraryTarget: 'var',
    library: '[name]',
  },

  plugins: [
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
    require('unplugin-element-plus/webpack')({
    }),
    new DefinePlugin({
      __VUE_OPTIONS_API__: true,
      __VUE_PROD_DEVTOOLS__: false,
    }),
    new BundleTracker({filename: './webpack-stats.json'}), // Required for django-webpack-loader
    new MiniCssExtractPlugin({
      filename: '[name]/[contenthash].css',
    }),
    new VueLoaderPlugin(),
  ],

  resolve: {
    modules: [
      path.resolve('.'),
      path.resolve('./node_modules'),
    ],
    fallback: {
      'path': require.resolve('path-browserify'),
    },
  },
}
