import { createApp } from 'vue'
import * as Sentry from '@sentry/vue'

import 'hunter2/js/base'
import AdminGuessList from './guess-list.vue'

const href = document.getElementById('admin-guess-list').dataset.href
const adminGuessList = createApp(AdminGuessList, {
  href: href,
})
adminGuessList.mixin(Sentry.createTracingMixins({ trackComponents: true }))
Sentry.attachErrorHandler(adminGuessList, { logErrors: true })
adminGuessList.mount('#admin-guess-list')
