import $ from 'jquery';

function hideInvite(list_entry) {
	"use strict";
	if (!list_entry.siblings().length) {
		$('#inv-div').hide('slow');
	}
	list_entry.fadeOut('slow', function() {
		$(this).remove();
	});
}

export function createInvite(event) {
	"use strict";
	event.preventDefault();
	var target = $(event.target);
	var field = target.find('select[name=user]');
	var user = field.val();
	var team = target.data('team');
	$.post(
		target.attr('action'), JSON.stringify({ user: user })
	).done(function(data) {
		$('#inv-error').text('').hide('fast');
		var cancel = $(`<a href="#" class="inv-cancel" data-user="${user}" onclick="cancelInvite()">Cancel</a>`);
		if (team) {
			cancel.data('team', team);
		}
		var list_entry = $(`<li style="display: none;">${data.username} has been invited<span style="float: right;">&nbsp;</span></li>`);
		list_entry.find('span').append(cancel);
		$('#inv-list').append(list_entry);
		list_entry.fadeIn('slow');
		field.empty();
	}).fail(function(jqXHR, textStatus, error) {
		var message = jqXHR.responseJSON.message;
		$('#inv-error').text(message).show('fast');
	});
}

export function cancelInvite(event) {
	"use strict";
	var target = $(event.target);
	var prefix = target.data('team') ? `${target.data('team')}/` : '';
	var list_entry = target.closest('li');
	$.post(
		prefix + 'cancelinvite', JSON.stringify({ user: target.data('user') })
	).done(function() {
		$('#inv-error').text('').hide('fast');
		hide_invite(list_entry);
	}).fail(function(jqXHR, textStatus, error) {
		var message = jqXHR.responseJSON.message;
		if (jqXHR.responseJSON['delete']) {
			hide_invite(list_entry);
		}
		$('#inv-error').text(message).show('fast');
	});
}

export function acceptInvite(event) {
	"use strict";
	var target = $(event.target);
	var prefix = target.data('team') ? `${target.data('team')}/` : '';
	var list_entry = target.closest('li');
	$.post(
		prefix + 'acceptinvite'
	).done(function() {
		location.reload();
	}).fail(function(jqXHR, textStatus, error) {
		var message = jqXHR.responseJSON.message;
		if (jqXHR.responseJSON['delete']) {
			hide_invite(list_entry);
		}
		$('#inv-error').text(message).show('fast');
	});
}

export function declineInvite(event) {
	"use strict";
	var target = $(event.target);
	var prefix = target.data('team') ? `${target.data('team')}/` : '';
	var list_entry = target.closest('li');
	$.post(
		prefix + 'denyinvite'
	).done(function() {
		$('#inv-error').text('').hide('fast');
		hide_invite(list_entry);
	}).fail(function(jqXHR, textStatus, error) {
		var message = jqXHR.responseJSON.message;
		if (jqXHR.responseJSON['delete']) {
			hide_invite(list_entry);
		}
		$('#inv-error').text(message).show('fast');
	});
}
