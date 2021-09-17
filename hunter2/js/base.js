import Vue from 'vue'

import AlertList from './alert-list.vue'

window.addEventListener('DOMContentLoaded', function() {
  const form = document.getElementById('logoutForm')
  if (form != null) {
    document.getElementById('logoutLink').addEventListener('click', function () {
      form.submit()
    })
  }

  window.alertList = new Vue({
    ...AlertList,
    data: {
      announcements: window.announcements,
      messages: window.messages,
    },
    el: '#alert-list',
  })
})
