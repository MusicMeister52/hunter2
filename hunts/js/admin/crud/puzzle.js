/* global $ */

import * as path from 'path'

import 'hunts/scss/admin/crud/puzzle.scss'

var advanced_shown

function toggleAdvanced(event, display, duration) {
  if (event !== undefined) {
    event.preventDefault()
  }

  let rows = $('.advanced_field').map(function() {
    return this.closest('div.form-row')
  })

  let columns = []
  $('.advanced_field').each(function(i, e) {
    let table = $(e).closest('table.djn-items')
    let column = $(e).closest('td.djn-td').prevAll().length + 1
    if (table !== undefined && column !== undefined) {
      columns.push([table, column])
      return
    }
  })

  if (display != undefined) {
    advanced_shown = display
  } else {
    advanced_shown = !rows.is(':visible')
  }

  if (duration == undefined) {
    duration = 'slow'
  }

  let button_verb
  if (advanced_shown) {
    button_verb = 'Hide'
    $(rows).show(duration)
    columns.forEach(function(table_column) {
      let table = $(table_column[0])
      let column = table_column[1]
      let cells = table.find(`td:nth-child(${column}),th:nth-child(${column})`)
      cells.show(duration)
    })
  } else {
    button_verb = 'Show'
    $(rows).hide(duration)
    columns.forEach(function(table_column) {
      let table = $(table_column[0])
      let column = table_column[1]
      let cells = table.find(`td:nth-child(${column}),th:nth-child(${column})`)
      cells.hide(duration)
    })
  }

  $('#advanced_button').html(`${button_verb} Advanced Options`)
}

function copyPermalinkClicked(e) {
  e.preventDefault()

  // Browsers don't let you just manipulate the clipboard (yet) so we create an
  // invisible element to hold the text, select it, then call the browser's
  // 'copy' command.
  var tmp = $('<input>')
  tmp.css('position', 'fixed')
  tmp.css('top', 0)
  tmp.css('left', -99999)
  $('body').append(tmp)

  tmp.val(e.target.href).select()
  document.execCommand('copy')
  tmp.remove()
}

function fileInputChanged(e) {
  let inputGroup = e.target.id.split('-file')[0]
  let slugInput = document.getElementById(`${inputGroup}-slug`)
  let urlInput = document.getElementById(`${inputGroup}-url_path`)

  let filename = e.target.files[0].name

  if (!slugInput.value) {
    // slugs must be ASCII alphanumeric strings (including underscores) that
    // start with an underscore or letter
    slugInput.value = path.parse(filename).name
      .replace(/[^a-zA-Z_0-9]/g, '')
      .replace(/^(?:[0-9])/, '_')
  }
  if (!urlInput.value) {
    urlInput.value = filename
  }
}

$(function() {
  toggleAdvanced(undefined, false, 0)
  $(document).on('DOMNodeInserted', function(e) {
    // When a DOM node is inserted, check if it contains advanced fields
    let advanced_fields = $(e.target).find('.advanced_field')
    if (!advanced_shown && advanced_fields.length) {
      toggleAdvanced(undefined, false, 0)
    }
    e.target.querySelectorAll('input[type="file"]').forEach(el => {
      el.addEventListener('change', fileInputChanged)
    })
  })
  document.querySelectorAll('input[type="file"]').forEach(el => {
    el.addEventListener('change', fileInputChanged)
  })
  $('#advanced_button').click(toggleAdvanced)
  $('.puzzlepermalink').click(copyPermalinkClicked)
})
