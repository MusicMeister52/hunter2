import $ from 'jquery'
import 'bootstrap'

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
    })
  })

  var hash = window.location.hash ? window.location.hash : '#episode-1'
  $(`#ep-list a[href="${hash}"`).tab('show')
})
