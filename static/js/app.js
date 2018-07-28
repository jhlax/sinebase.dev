const app = angular.module('sinebase_app', ['ngMaterial', 'ngMessages', 'ngRoute',
    'ngStorage', 'md.data.table']);

app.config(function ($mdThemingProvider) {
    $mdThemingProvider.theme('default')
        .primaryPalette('blue')
        .accentPalette('blue-grey')
    ;
});


app.config(['$httpProvider', function ($httpProvider) {
    if (!$httpProvider.defaults.headers.get) {
        $httpProvider.defaults.headers.get = {};
    }
    // Answer edited to include suggestions from comments
    // because previous version of code introduced browser-related errors

    //disable IE ajax request caching
    // $httpProvider.defaults.headers.get['If-Modified-Since'] = 'Mon, 26 Jul 1997 05:00:00 GMT';
    // // extra
    // $httpProvider.defaults.headers.get['Cache-Control'] = 'no-cache';
    // $httpProvider.defaults.headers.get['Pragma'] = 'no-cache';
}]);

app.config(function ($locationProvider) {
    $locationProvider
        .html5Mode({
            enabled: true,
            requireBase: false
        });
});

app.config(function ($routeProvider) {
    $routeProvider
        .when('/', {
            templateUrl: '/static/partials/home.html',
            controller: 'home_ctl',
            controllerAs: 'Home',
        })
        .when('/login', {
            templateUrl: '/static/partials/login.html',
            controller: 'login_ctl',
            controllerAs: 'Login',
        })
        .when('/users', {
            templateUrl: '/static/partials/users.html',
            controller: 'users_ctl',
            controllerAs: 'Users'
        })
        .when('/users/new', {
            templateUrl: '/static/partials/user.html',
            controller: 'user_ctl',
            controllerAs: 'User',
        })
        .when('/users/u/:user_id', {
            templateUrl: '/static/partials/user.html',
            controller: 'user_ctl',
            controllerAs: 'User',
        })
        .when('/case/new', {
            templateUrl: '/static/partials/case.html',
            controller: 'case_ctl',
            controllerAs: 'Case',
        })
        .when('/case/c/:case_id', {
            templateUrl: '/static/partials/case.html',
            controller: 'case_ctl',
            controllerAs: 'Case',
        })
        .when('/whitepaper', {
            templateUrl: '/static/partials/whitepaper.html',
        });
});


app.service('Site', ['$localStorage', function ($localStorage) {
    let Site = this;

    Site.get_token = function () {
        console.info('Retrieving token: ' + $localStorage.token);
        return $localStorage.token;
    };

    Site.set_token = function (token) {
        console.info('Setting token: ' + token);
        $localStorage.token = token;
        console.info('Token set: ' + $localStorage.token);
    };

    Site.get_user = function () {
        return $localStorage.user;
    };

    Site.set_user = function (user) {
        $localStorage.user = user;
    };

    Site.is_logged_in = function () {
        return angular.isDefined($localStorage.user);
    }
}]);

app.service('REST', ['Site', '$http', function (Site, $http) {
    let REST = this;

    REST.get_headers = function () {
        console.info(Site.get_token());
        return {
            'headers': {
                'Token': Site.get_token(),
                'If-Modified-Since': 'Mon, 26 Jul 1997 05:00:00 GMT',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        };
    };

    REST.get = function (endpoint) {
        return $http.get(endpoint, REST.get_headers());
    };

    REST.post = function (endpoint, data) {
        return $http.post(endpoint, data, REST.get_headers());
    };

    REST.delete = function (endpoint) {
        return $http.delete(endpoint, REST.get_headers());
    };

    Site.REST = REST;
}]);


app.controller('app_ctl', ['Site', 'REST', '$location', '$localStorage', function (Site, REST, $location, $localStorage) {
    /*
    Site-wide controller
     */
    let App = this;
    App.site = Site;
    App.name = 'TBG CTS (DEV)';

    App.title = '';
    App.track = {
        'bpm': 128,
        'key': 'C',
        'scale': 'major'
    };

    App.logout = function () {
        REST.delete('/api/auth').then(function (res) {
            $localStorage.$reset();
            $location.path('/login');
        });
    };

    App.goto = function (page) {
        $location.path(page);
    };

    App.init = function () {
        REST.get('/api/auth').then(function (res) {
            data = res.data;
            if (data.result === 'success') {
                console.log('Validation successful.');
                Site.set_token(data.data.token);
                Site.set_user(data.data.user);
            } else {
                console.log('Validation unsuccessful.\n' + JSON.stringify(res));
                App.logout();
            }
        });
        Site.app_ctl = App;
    };

    App.init();
}]);

app.controller('home_ctl', ['Site', 'REST', function (Site, REST) {
    /*
    Home controller
     */
    let Home = this;
    Site.home_ctl = Home;

    Home.Site = Site;
    Home.whitepaper = false;

    Home.get_cases = function () {
        REST.get('/api/cases').then(function suc(response) {
            Home.cases = response.data.data;
        }, function fail(response) {
            Home.message = response.data.message;
        });
    };

    Home.init = function () {
        Site.app_ctl.title = ': Home';
        Home.get_cases();
    };

    Home.init();
}]);

app.controller('login_ctl', ['Site', '$http', '$location', function (Site, $http, $location) {
    let Login = this;

    Login.login = function () {
        if (Login.email && Login.password) {
            $http.post('/api/auth', {
                'email': Login.email,
                'password': sha256(Login.password)
            }, {}).then(function (res) {
                let data = res.data;
                if (data.result === 'success') {
                    Site.set_token(data.data.token);
                    Site.set_user(data.data.user);
                    $location.path('/');
                } else {
                    Login.error = data.message;
                }
            });
        } else {
            Login.error = 'You must enter a valid email and password.';
        }
    };

    Login.init = function () {
        Site.app_ctl.title = ': Login';
    };

    Login.init();
}]);

app.controller('users_ctl', ['Site', 'REST', function (Site, REST) {
    let Users = this;
    Site.users_ctl = Users;

    Users.selected = [];

    Users.update_list = function () {
        let req = REST.get('/api/users');

        req.then(function (res) {
            let data = res.data;
            if (data.result === 'success') {
                Users.list = data.data;
            } else {
                Users.list = [];
            }
        });

        Users.promise = req.$promise;
    };

    Users.init = function () {
        Site.app_ctl.title = ': Users';
        Users.update_list();
    };

    Users.init();
}]);

app.controller('user_ctl', ['Site', 'REST', '$routeParams', '$location',
    function (Site, REST, $routeParams, $location) {
        let User = this;
        Site.user_ctl = User;

        User.levels = ['viewer', 'regular', 'admin', 'super'];
        User.old = {};

        User.edit = function () {
            User.old = angular.copy(User.data);
            User.is_edit = !User.is_edit;
        };

        User.exit = function () {
            Site.app_ctl.goto('/users');
        };

        User.cancel = function () {
            if (User.action === 'new') {
                User.exit();
            } else {
                User.data = angular.copy(User.old);
                User.edit();
            }
        };

        User.save = function () {
            if (User.data.name && User.data.email && User.data.level) {
                if (User.action === 'new') {
                    if (User.password && User.password1) {
                        if (User.password === User.password1) {
                            let req_data = angular.copy(User.data);

                            req_data.password = sha256(User.password);
                            REST.post('/api/users', req_data).then(
                                function (res) {
                                    let data = res.data;
                                    if (data.result === 'success') {
                                        Site.app_ctl.goto('/users');
                                    } else {
                                        User.error = data.message;
                                    }
                                }, function (res) {
                                    User.error = data.message;
                                }
                            );
                        } else {
                            User.error = 'Your passwords must match.';
                            return null;
                        }
                    } else {
                        User.error = 'You must enter a password.';
                        return null;
                    }
                } else {
                    REST.post('/api/users/' + User.user_id, User.data).then(
                        function (res) {
                            let data = res.data;
                            if (data.result === 'success') {
                                Site.app_ctl.goto('/users');
                            } else {
                                User.error = data.message;
                            }
                        }
                    );
                }
            } else {
                User.error = 'Check required fields.';
            }
        };

        User.delete = function () {
            if (User.user_id) {
                REST.delete('/api/users/' + User.user_id).then(
                    function (res) {
                        let data = res.data;

                        if (data.result === 'success') {
                            Site.app_ctl.goto('/users');
                        } else {
                            User.error = data.message;
                        }
                    }, function (res) {
                        User.error = 'Server error occured.';
                    }
                );
            }
        };

        User.get_user = function () {
            REST.get(User.endpoint).then(function (res) {
                data = res.data;
                if (data.result === 'success') {
                    User.data = data.data;
                    Site.app_ctl.title = ': ' + User.data.name;
                } else {
                    User.error = data.message;
                }
            });
        };

        User.init = function () {
            if ('user_id' in $routeParams) {
                User.user_id = $routeParams.user_id;
                User.endpoint = '/api/users/' + User.user_id;
                User.action = 'update';
                User.is_edit = true;
                User.get_user();
            } else {
                User.endpoint = '/api/users/';
                User.action = 'new';
                User.is_edit = false;
                Site.app_ctl.title = ': New User';
            }
        };

        User.init();
    }]);

app.controller('case_ctl', ['Site', 'REST', '$routeParams', function (Site, REST, $routeParams) {
    let Case = this;

    Case.get_case = function () {
        REST.get(Case.endpoint).then(function (res) {
            Case.data = res.data.data;
        });
    };

    Case.init = function () {
        Site.app_ctl.title = ': Case';
        if ('case_id' in $routeParams) {
            Case.case_id = $routeParams.case_id;
            Case.endpoint = '/api/cases/' + Case.case_id;
            Case.is_edit = false;
            Case.get_case();
            Site.app_ctl.title = ': ' + Case.case_name + ' Case';
        } else {
            Case.endpoint = '/api/cases';
            Case.is_edit = true;
        }
    };

    Case.init();
}]);