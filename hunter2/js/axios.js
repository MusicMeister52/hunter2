// Thin helper to set up wrap importing axios and setting up Django CSRF
import axios from 'axios'

axios.defaults.xsrfCookieName = 'csrftoken'
axios.defaults.xsrfHeaderName = 'X-CSRFTOKEN'

export default axios
