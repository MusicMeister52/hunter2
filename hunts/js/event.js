import $ from 'jquery'
import 'bootstrap'
import DateTime from 'luxon/src/datetime'
import * as LuxonFormats from 'luxon/src/impl/formats'

import 'hunter2/js/base'

/* global eventTitle */

$(function () {
  $('a[data-toggle="tab"]').on('show.bs.tab', function () {
    var url = $(this).data('url')
    var target = $(this).attr('href')
    var tab = $(this)
    $(target).load(url, function () {
      tab.tab('show')
      history.pushState({}, '', '#' + target.substr(1))
      window.document.title = tab.text() + ' - ' + eventTitle

      document.querySelectorAll('span.localtime').forEach(elt => {
        let dt = DateTime.fromISO(elt.dataset.utc)
        let fmt = elt.dataset.format
        if (!Object.prototype.hasOwnProperty.call(LuxonFormats, fmt)) {
          throw new Error(`${fmt} is not a valid Luxon format preset`)
        }

        let text = dt.toLocaleString(DateTime[fmt])
        elt.parentNode.replaceChild(document.createTextNode(text), elt)
      })
    })
  })

  var hash = window.location.hash ? window.location.hash : '#episode-1'
  $(`#ep-list a[href="${hash}"`).tab('show')
})
