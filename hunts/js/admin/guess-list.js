import { Pagination } from 'element-ui'
import 'element-ui/lib/theme-chalk/index.css'
import lang from 'element-ui/lib/locale/lang/en'
import locale from 'element-ui/lib/locale'
import URI from 'urijs'

import HumanDateTime from '../human-datetime.vue'
import HumanDuration from '../human-duration.vue'

locale.use(lang)

export default {
  components: {
    'el-pagination': Pagination,
    'human-datetime': HumanDateTime,
    'human-duration': HumanDuration,
  },
  created: function() {
    this.updateData(true)
  },
  data: function() {
    let search = URI(window.location).search(true)
    let page = 'page' in search ? search.page : 1
    delete search.page
    return {
      autoUpdate: true,
      currentPage: page,
      filter: search,
      guesses: [],
      rows: 0,
    }
  },
  methods: {
    changePage: function(page) {
      this.autoUpdate = page === 1
      this.currentPage = page
      let new_uri = URI(window.location)
      if (page == 1) {
        new_uri.removeSearch('page')
      } else {
        new_uri.setSearch('page', page)
      }
      window.history.pushState('', '', new_uri)
      this.updateData(true)
    },
    addFilter: function(type, value) {
      this.filter[type] = value
      this.currentPage = 1
      let new_uri = URI(window.location).setSearch(type, value).removeSearch('page')
      window.history.pushState('', '', new_uri)
      this.updateData(true)
    },
    clearFilters: function() {
      this.autoUpdate = true
      this.currentPage = 1
      this.filter = {}
      let new_uri = URI(window.location).search({})
      window.history.pushState('', '', new_uri)
      this.updateData(true)
    },
    updateData: function(force) {
      clearTimeout(this.timer)
      let page = this.currentPage
      if (force || this.autoUpdate) {
        let guesses_url = URI(this.href).search({...this.filter, 'page': page})
        let v = this
        fetch(guesses_url).then(
          response => response.json(),
        ).then(
          data => {
            v.guesses = data.guesses
            v.rows = data.rows
          },
        )
        if (this.autoUpdate) {
          this.timer = setTimeout(this.updateData, 5000)
        }
      }
    },
  },
  props: {
    href: {
      type: String,
      required: true,
    },
    perPage: {
      default: 50,
      type: Number,
    },
  },
  watch: {
    autoUpdate: function(on) {
      if (on) {
        this.updateData()
      }
    },
  },
}
