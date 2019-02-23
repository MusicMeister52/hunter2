import $ from 'jquery';

function hideRequest(list_entry) {
	"use strict";
	if (!list_entry.siblings().length) {
		$('#req-div').hide('slow');
	}
	list_entry.fadeOut('slow', function() {
		$(this).remove();
	});
}

export function createRequest(event) {
	"use strict";
	event.preventDefault();
	var target = $(event.target);
	var field = target.find('select[name=team]');
	var team = field.val();
	$.post(
		team + '/request'
	).done(function(data) {
		$('#inv-error').text('').hide('fast');
		var cancel_link = $(`<a href="#" data-team="${team}" onclick="cancelRequest()">Cancel</a>`);
		var list_entry = $(`<li style="display: none;">You have requested to join ${data.team}<span style="float: right;"></span></li>`);
		list_entry.find('span').append(cancel_link);
		$('#req-list').append(list_entry);
		list_entry.fadeIn('slow');
	}).fail(function(jqXHR, textStatus, error) {
		var message = jqXHR.responseJSON.message;
		if (jqXHR.responseJSON['delete']) {
			list_entry.fadeOut('slow', function() {
				$(this).remove();
			});
		}
		$('#req-error').text(message).show('fast');
	});
}

export function cancelRequest(event) {
	"use strict";
	var target = $(event.target);
	var list_entry = target.closest('li');
	var list = target.closest('ul');
	$.post(
		target.data('team') + '/cancelrequest'
	).done(function() {
		$('#req-error').text('').hide('fast');
		hideRequest(list_entry);
	}).fail(function(jqXHR, textStatus, error) {
		var message = jqXHR.responseJSON.message;
		if (jqXHR.responseJSON['delete']) {
			hideRequest(list_entry);
		}
		$('#req-error').text(message).show('fast');
	});
}

export function acceptRequest(event) {
	"use strict";
	var target = $(event.target);
	var prefix = target.data('team') ? `${target.data('team')}/` : '';
	var list_entry = target.closest('li');
	$.post(
		prefix + 'acceptrequest', JSON.stringify({ user: target.data('user') })
	).done(function(data) {
		$('#req-error').text('').hide('fast');
		hideRequest(list_entry);
		var new_element = $(`<li>${data.username}<span style="float: right">&nbsp;${data.seat}</span></li>`);
		$('#member-list').append(new_element);
	}).fail(function(jqXHR, textStatus, error) {
		var message = jqXHR.responseJSON.message;
		if (jqXHR.responseJSON['delete']) {
			hideRequest(list_entry);
		}
		$('#req-error').text(message).show('fast');
	});
}

export function declineRequest(event) {
	"use strict";
	var target = $(event.target);
	var prefix = target.data('team') ? `${target.data('team')}/` : '';
	var list_entry = target.closest('li');
	$.post(
		prefix + 'denyrequest', JSON.stringify({ user: target.data('user') })
	).done(function() {
		$('#req-error').text('').hide('fast');
		hideRequest(list_entry);
	}).fail(function(jqXHR, textStatus, error) {
		var message = jqXHR.responseJSON.message;
		if (jqXHR.responseJSON['delete']) {
			hideRequest(list_entry);
		}
		$('#req-error').text(message).show('fast');
	});
}
