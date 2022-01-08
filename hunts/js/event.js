import Tab from 'bootstrap/js/dist/tab'

import {formatDatesForLocalTZ} from 'hunter2/js/base'

/* global eventTitle */

document.addEventListener('DOMContentLoaded', function () {
  const triggerTabList = [].slice.call(document.querySelectorAll('#ep-list button'))
  triggerTabList.forEach(item => {
    item.addEventListener('show.bs.tab', function (event) {
      const url = event.target.dataset.url
      const targetPaneID = event.target.dataset.bsTarget
      fetch(url).then(data => {
        return data.text()
      }).then(data => {
        const targetPane = document.querySelector(targetPaneID)
        targetPane.innerHTML = data
        formatDatesForLocalTZ()
      })
    }, { once: true })
    item.addEventListener('shown.bs.tab', function (event) {
      const targetPaneID = event.target.dataset.bsTarget
      history.pushState({}, '', targetPaneID)
      window.document.title = event.target.text() + ' - ' + eventTitle
    })
  })

  const hash = window.location.hash ? window.location.hash : '#episode-1'
  const tab = new Tab(document.getElementById(`${hash.substr(1)}-tab`))
  tab.show()
})
