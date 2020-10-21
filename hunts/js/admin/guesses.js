import 'bootstrap'
import Vue from 'vue'

import 'hunter2/js/base'
import AdminGuessList from './guess-list.vue'

const href = document.getElementById('admin-guess-list').dataset.href
const adminguesslist = new Vue({
  ...AdminGuessList,
  propsData: {
    href: href,
  },
})
adminguesslist.$mount('#admin-guess-list')
