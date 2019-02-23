import '../scss/base.scss';

import 'bootstrap';
import setupJQueryAjaxCsrf from './csrf';

// Expose global $ for jquery for now
require("expose-loader?$!jquery");

// TODO: Look at the best practice way of doing this.
setupJQueryAjaxCsrf();
