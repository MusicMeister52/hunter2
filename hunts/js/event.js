document.addEventListener('DOMContentLoaded', function () {
  "use strict";

  $('a[data-toggle="tab"]').on('show.bs.tab', function (e) {
    var url = $(this).data('url');
    var target = $(this).attr('href');
    var tab = $(this);
    $(target).load(url, function (result) {
      tab.tab('show');
      window.location.hash = target.substr(1);
    });
  });

  var hash = window.location.hash ? window.location.hash : '#episode-1';
  $(`#ep-list a[href="${hash}"`).tab('show');
});
