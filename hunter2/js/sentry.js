import * as Sentry from '@sentry/browser'

if (window.sentry_dsn) {
  Sentry.init({
    dsn: window.sentry_dsn,
    integrations: [
      new Sentry.Integrations.Vue(),
    ],
  })
}
