import {createApp, reactive} from 'vue'
import * as Sentry from '@sentry/vue'
import 'bootstrap/js/dist/collapse'

import AlertList from './alert-list.vue'

import {DateTime} from 'luxon'

export function formatDatesForLocalTZ() {
  document.querySelectorAll('span.localtime').forEach(elt => {
    let dt = DateTime.fromISO(elt.dataset.utc)
    let fmt = elt.dataset.format
    let text = dt.toLocaleString(DateTime[fmt])
    elt.parentNode.replaceChild(document.createTextNode(text), elt)
  })
}

window.addEventListener('DOMContentLoaded', function() {
  const form = document.getElementById('logoutForm')
  if (form != null) {
    document.getElementById('logoutLink').addEventListener('click', function () {
      form.submit()
    })
  }

  window.announcements = reactive(window.announcements)
  window.messages = reactive(window.messages)

  window.alertList = createApp(
    AlertList,
    {
      announcements: window.announcements,
      messages: window.messages,
    },
  )
  window.alertList.mixin(Sentry.createTracingMixins({ trackComponents: true }))
  Sentry.attachErrorHandler(window.alertList, { logErrors: true })
  window.alertList.mount('#alert-list')

  formatDatesForLocalTZ()
})
