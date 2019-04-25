/* global $ */

import '../scss/admin_puzzle.scss'

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

$(function() {
  toggleAdvanced(undefined, false, 0)
  $(document).on('DOMNodeInserted', function(e) {
    // When a DOM node is inserted, check if it contains advanced fields
    let advanced_fields = $(e.target).find('.advanced_field')
    if (!advanced_shown && advanced_fields.length) {
      toggleAdvanced(undefined, false, 0)
    }
  })
  $('#advanced_button').click(toggleAdvanced)
})
