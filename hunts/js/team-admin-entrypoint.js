import Vue from 'vue'
import App from './team-admin.vue'
import vueMoment from 'vue-moment'

Vue.use(vueMoment)

const el = document.getElementById('team_puzzles_admin_widget')

new Vue({
  el: el,
  render: h => h(App, {
    props: {
      href: el.attributes.href.value,
    },
  }),
})
