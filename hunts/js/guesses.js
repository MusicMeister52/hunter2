import $ from 'jquery'
import 'bootstrap'
import Vue from 'vue'

import AdminGuessList from './admin-guess-list.vue'
import setupJQueryAjaxCsrf from 'hunter2/js/csrf.js'

$(function () {
  setupJQueryAjaxCsrf()

  const href = $('#admin-guess-list').data('href')
  const adminguesslist = new Vue({
    ...AdminGuessList,
    propsData: {
      href: href,
    },
  })
  adminguesslist.$mount('#admin-guess-list')
})
