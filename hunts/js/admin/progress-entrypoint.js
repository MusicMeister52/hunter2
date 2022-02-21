import { createApp } from 'vue'
import * as Sentry from '@sentry/vue'

import Progress from './progress.vue'

const el = document.getElementById('admin_progress_widget')

const progress = createApp(Progress, {
  href: el.attributes.href.value,
})
progress.mixin(Sentry.createTracingMixins({ trackComponents: true }))
Sentry.attachErrorHandler(progress, { logErrors: true })
progress.mount(el)
