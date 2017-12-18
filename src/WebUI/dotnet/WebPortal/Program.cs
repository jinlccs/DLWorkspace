using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Hosting;
<<<<<<< HEAD
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Configuration;


=======
using Microsoft.Extensions.Configuration;

>>>>>>> 7da9f8ff12a752b92e50eaf8896a32d515d66c36
namespace WindowsAuth
{
    public class Program
    {
        // Entry point for the application.
        public static void Main(string[] args)
<<<<<<< HEAD
        {
            var config = new ConfigurationBuilder()
                .SetBasePath(Directory.GetCurrentDirectory())
                .AddJsonFile("hosting.json", optional: true)
                .Build();

            var host = new WebHostBuilder()
                .UseUrls("http://*:80;")
                .UseConfiguration(config)
                .UseKestrel()
                .UseContentRoot(Directory.GetCurrentDirectory())
                .UseIISIntegration()
                .UseStartup<Startup>()
                .Build();

            host.Run();

            /*
=======
        {
            var config = new ConfigurationBuilder()
                .SetBasePath(Directory.GetCurrentDirectory())
                .AddJsonFile("hosting.json", optional: true)
                .Build();

>>>>>>> 7da9f8ff12a752b92e50eaf8896a32d515d66c36
            var host = new WebHostBuilder()
                .UseUrls("http://0.0.0.0:80")
                .UseConfiguration(config)
                .UseKestrel()
                .UseContentRoot(Directory.GetCurrentDirectory())
                .UseIISIntegration()
                .UseStartup<Startup>()
                .Build();

            host.Run(); */
        }
    }
}
