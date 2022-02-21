import { createApp } from 'vue'
import Team from './team.vue'
import * as Sentry from '@sentry/vue'

const el = document.getElementById('team_puzzles_admin_widget')

const team = createApp(Team, {
  href: el.attributes.href.value,
})
team.mixin(Sentry.createTracingMixins({ trackComponents: true }))
Sentry.attachErrorHandler(team, { logErrors: true })
team.mount(el)
